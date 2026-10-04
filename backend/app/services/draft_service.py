"""Draft studio: generation, versioned edits, and persistence.

Every write lands in one Firestore document under the project subtree
(`users/{uid}/projects/{projectId}/draft/main`), so the existing recursive project /
account delete path already removes it. The LLM only ever *proposes* text; this
service turns a proposal into a new immutable version on a block, so nothing the
creator typed is ever overwritten.
"""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.errors import BadRequestError
from app.providers.base import LlmProvider
from app.schemas.draft import (
    AssistDraftRequest,
    AssistMode,
    Draft,
    DraftBlock,
    DraftBlockType,
    DraftBrief,
    DraftFormat,
    DraftMessage,
    DraftStatus,
    DraftSummary,
    DraftVersion,
    GenerateDraftRequest,
    SaveDraftRequest,
    SuggestDraftRequest,
    SuggestMode,
)
from app.schemas.projects import ProjectStatus
from app.services.channel_content_service import ChannelContentService
from app.services.firestore_service import FirestoreClient, draft_path
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

DRAFT_GENERATE_PROMPT_VERSION = "draft-generate-v1"
DRAFT_ASSIST_PROMPT_VERSION = "draft-assist-v1"
DRAFT_SUGGEST_PROMPT_VERSION = "draft-suggest-v1"

GENERATE_SYSTEM = (
    "You are a senior editor and scriptwriter inside a creator studio. Turn the creator's "
    "brief into a strong first draft they can edit.\n"
    "Rules:\n"
    "- Write in the requested language and voice. Never invent facts, statistics, or quotes.\n"
    "- Structure the draft with short, purposeful blocks. Use type `heading` for section "
    "titles, `paragraph` for prose, and `scene` for individual beats of a video script "
    "(each scene is one shootable moment with a clear visual or spoken beat).\n"
    "- Open with a hook that earns the next sentence. No throat-clearing.\n"
    "- Be concrete. Prefer examples and specifics over adjectives and filler.\n"
    "- When `creatorContext` is present, match the creator's established voice and structure: "
    "study the example titles, tags, and descriptions and write in the same register and reading "
    "level. Treat them as style evidence only — never copy a title or invent claims from them.\n"
    "- Do not add meta commentary, labels, or markdown syntax inside `text`."
)

ASSIST_SYSTEM = (
    "You are the creator studio's writing partner. You help revise a versioned draft while "
    "preserving the creator's intent and voice.\n"
    "You answer with JSON only.\n"
    "- `reply`: a short, direct note to the creator explaining what you changed. No preamble.\n"
    "- `title`: a better title when the instruction implies one, otherwise an empty string.\n"
    "- `clearDraft`: true only when the creator explicitly asks to clear, empty, delete, or "
    "start over from a blank draft. It removes every block.\n"
    "- `removeBlockIds`: ids of existing blocks to delete (e.g. 'drop the intro').\n"
    "- `blocks`: the edits to apply. To revise an existing block, set `blockId` to its exact id "
    "from the context and put the full replacement text in `text` with a short `label` (e.g. "
    "`Punchier`). To add a new block, leave `blockId` empty and set `type` to `heading` or "
    "`paragraph`. Never fabricate block ids.\n"
    "Every entry becomes a new version, so the previous wording is always kept — write the "
    "complete new text for the block, not a diff.\n"
    "When asked for alternatives, return several entries with the same `blockId`, one per "
    "alternative. Never invent facts, numbers, or quotes.\n"
    "CRITICAL: your `reply` must only describe changes you actually returned in `clearDraft`, "
    "`removeBlockIds`, or `blocks`. If you say you cleared the draft, set `clearDraft` to true. "
    "If the creator asked for a change and you have no edit to return, say so instead of "
    "claiming you did it."
)

GENERATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [item.value for item in DraftBlockType],
                    },
                    "text": {"type": "string"},
                },
                "required": ["type", "text"],
            },
        },
    },
    "required": ["title", "blocks"],
}

ASSIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "title": {"type": "string"},
        "clearDraft": {"type": "boolean"},
        "removeBlockIds": {"type": "array", "items": {"type": "string"}},
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "blockId": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [item.value for item in DraftBlockType],
                    },
                    "text": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
    "required": ["reply"],
}

SUGGEST_SYSTEM = (
    "You rewrite one short span of a draft at a time, at the creator's request. "
    "You answer with JSON only: `suggestions`, an ordered list of replacement "
    "strings for the selected span.\n"
    "- Return exactly the requested number of suggestions, each a drop-in replacement "
    "for the selection that keeps the surrounding sentence grammatical.\n"
    "- Keep the creator's voice and meaning. Change only the selected words.\n"
    "- Never invent facts, numbers, names, or quotes.\n"
    "- Do not add quotes, labels, or commentary inside a suggestion."
)

SUGGEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "suggestions": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["suggestions"],
}


def _new_id() -> str:
    return uuid4().hex[:12]


_TAG = re.compile(r"<[^>]+>")
_MARKER_RUN = re.compile(r"^[*@~]+")


def _find_variants(text: str) -> list[tuple[int, int, str]]:
    r"""Find `{{…}}` groups, tolerating single braces inside the option text.

    The old `/\{\{([^{}]*)\}\}/` regex could not parse an alternative whose text
    contained `{` or `}` — e.g. a code snippet — so the raw `{{…}}` leaked into word
    counts, summaries, and the AI context. A depth-aware scan treats a `{`/`}` inside
    the group as content and only ends it at a `}}` seen at depth 0.
    """
    spans: list[tuple[int, int, str]] = []
    i = 0
    n = len(text)
    while i < n - 1:
        if text[i] == "{" and text[i + 1] == "{":
            depth = 0
            j = i + 2
            end = -1
            while j < n:
                ch = text[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    if depth == 0 and j + 1 < n and text[j + 1] == "}":
                        end = j
                        break
                    if depth > 0:
                        depth -= 1
                j += 1
            if end != -1:
                spans.append((i, end + 2, text[i + 2 : end]))
                i = end + 2
                continue
        i += 1
    return spans


def resolve_variants(text: str) -> str:
    """Replace every `{{…}}` group with its active option."""
    spans = _find_variants(text)
    if not spans:
        return text
    parts: list[str] = []
    last = 0
    for start, end, inner in spans:
        parts.append(text[last:start])
        parts.append(active_variant_text(inner))
        last = end
    parts.append(text[last:])
    return "".join(parts)


def _strip_markers(option: str) -> str:
    return _MARKER_RUN.sub("", option.strip()).strip()


def _is_active_option(option: str) -> bool:
    markers = _MARKER_RUN.match(option.strip())
    return bool(markers and "*" in markers.group(0))


def active_variant_text(inner: str) -> str:
    options = [part.strip() for part in inner.split("|") if part.strip()]
    active = next(
        (option for option in options if _is_active_option(option)),
        options[0] if options else "",
    )
    return _strip_markers(active)


def strip_html(text: str) -> str:
    """Plain text for word counts, prompts, and summaries.

    Block text is Markdown and may contain inline alternatives
    (`{{original | ~*ai version | @my version}}`). Each option may carry markers
    (`*` active, `~` AI, `@` user) and the original has none. Anything that
    reasons about the words resolves to the active option and strips the markers
    before stripping any HTML.
    """
    text = resolve_variants(text)
    if "<" not in text:
        return text.strip()
    plain = _TAG.sub(" ", text)
    plain = (
        plain.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return re.sub(r"\s+", " ", plain).strip()


def word_count(text: str) -> int:
    return len(strip_html(text).split())


def active_text(block: DraftBlock) -> str:
    for version in block.versions:
        if version.versionId == block.activeVersionId:
            return version.text
    return block.versions[0].text if block.versions else ""


def build_summary(draft: Draft) -> DraftSummary:
    words = 0
    versions = 0
    for block in draft.blocks:
        words += word_count(active_text(block))
        versions += len(block.versions)
    preview = " ".join(
        strip_html(active_text(block)) for block in draft.blocks[:2]
    ).strip()
    return DraftSummary(
        title=draft.title,
        preview=preview[:200],
        wordCount=words,
        blockCount=len(draft.blocks),
        versionCount=versions,
    )


def _make_block(
    *, type_: DraftBlockType, text: str, label: str, origin: str = "assistant"
) -> DraftBlock:
    version = DraftVersion(
        versionId=_new_id(),
        text=text.strip(),
        label=label,
        origin=origin,
        createdAt=datetime.now(UTC),
    )
    return DraftBlock(
        blockId=_new_id(),
        type=type_,
        versions=[version],
        activeVersionId=version.versionId,
    )


def _fallback_blocks(brief: DraftBrief) -> list[DraftBlock]:
    """A deterministic, honest first draft when the model is unavailable."""
    topic = brief.topic.strip() or "your idea"
    hook = f"Here is the shortest version of {topic} that still works."
    blocks = [
        _make_block(type_=DraftBlockType.heading, text=topic, label="Draft"),
        _make_block(type_=DraftBlockType.paragraph, text=hook, label="Draft"),
    ]
    if brief.audience.strip():
        blocks.append(
            _make_block(
                type_=DraftBlockType.paragraph,
                text=f"For {brief.audience.strip()}, start with the pain they already feel.",
                label="Draft",
            )
        )
    if brief.tone.strip():
        blocks.append(
            _make_block(
                type_=DraftBlockType.paragraph,
                text=f"Keep the tone {brief.tone.strip()} throughout.",
                label="Draft",
            )
        )
    return blocks


def _looks_like_clear(message: str) -> bool:
    """True when the creator clearly asked to wipe the draft."""
    text = message.lower()
    verbs = ("clear", "empty", "erase", "wipe", "delete", "remove", "reset")
    nouns = ("draft", "everything", "all", "content", "document", "text")
    if "start over" in text or "from scratch" in text or "blank" in text:
        return True
    return any(verb in text for verb in verbs) and any(
        noun in text for noun in nouns
    )


class DraftService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        projects: ProjectService,
        llm: LlmProvider,
        settings: Settings,
        content: ChannelContentService | None = None,
    ) -> None:
        self.client = client
        self.projects = projects
        self.llm = llm
        self.settings = settings
        self.content = content

    # ------------------------------------------------------------------ reads

    def get(self, *, owner_uid: str, project_id: str) -> Draft:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        data = self.client.get_document(draft_path(owner_uid, project_id))
        if data is None:
            return Draft(projectId=project_id)
        return self._to_draft(project_id, data)

    def ensure(
        self,
        *,
        owner_uid: str,
        project_id: str,
        brief: DraftBrief,
        format_: DraftFormat,
    ) -> Draft:
        """Seed the draft document when a draft project is created."""
        existing = self.client.get_document(draft_path(owner_uid, project_id))
        if existing is not None:
            return self._to_draft(project_id, existing)
        draft = Draft(projectId=project_id, brief=brief.model_copy(update={"format": format_}))
        self._persist(owner_uid=owner_uid, draft=draft, status=ProjectStatus.draft)
        return draft

    # ----------------------------------------------------------------- writes

    def save(
        self, *, owner_uid: str, project_id: str, payload: SaveDraftRequest
    ) -> Draft:
        draft = self.get(owner_uid=owner_uid, project_id=project_id)
        if payload.title is not None:
            draft.title = payload.title.strip()[:200]
        # The client always sends the full block set, so an explicit empty list
        # means "I deleted everything" and must clear the draft. Only an omitted
        # field leaves the blocks untouched.
        if "blocks" in payload.model_fields_set:
            draft.blocks = payload.blocks
        status = (
            ProjectStatus.draft if not draft.blocks else ProjectStatus.ready
        )
        self._persist(owner_uid=owner_uid, draft=draft, status=status)
        return draft

    async def generate(
        self,
        *,
        owner_uid: str,
        project_id: str,
        overrides: GenerateDraftRequest,
    ) -> Draft:
        draft = self.get(owner_uid=owner_uid, project_id=project_id)
        draft.brief = self._apply_overrides(draft.brief, overrides)
        draft.status = DraftStatus.generating
        self._persist(owner_uid=owner_uid, draft=draft, status=ProjectStatus.processing)

        blocks = await self._generate_blocks(draft.brief, draft, owner_uid=owner_uid)
        draft.blocks = blocks
        draft.messages = [
            DraftMessage(
                messageId=_new_id(),
                role="assistant",
                content=(
                    "Here is a first draft based on your brief. Every paragraph keeps its "
                    "history — ask me to sharpen a line, or use Alternatives to compare "
                    "wordings side by side."
                ),
                createdAt=datetime.now(UTC),
            )
        ]
        draft.status = DraftStatus.ready
        draft.error = None
        self._persist(owner_uid=owner_uid, draft=draft, status=ProjectStatus.ready)
        return draft

    async def assist(
        self, *, owner_uid: str, project_id: str, payload: AssistDraftRequest
    ) -> Draft:
        draft = self.get(owner_uid=owner_uid, project_id=project_id)
        now = datetime.now(UTC)
        draft.messages.append(
            DraftMessage(
                messageId=_new_id(),
                role="user",
                content=payload.message.strip(),
                createdAt=now,
            )
        )
        try:
            result = await self.llm.complete_json(
                model=self.settings.model_writer,
                prompt_version=DRAFT_ASSIST_PROMPT_VERSION,
                system=ASSIST_SYSTEM,
                user=self._assist_context(draft, payload),
                schema=ASSIST_SCHEMA,
            )
            reply, title, clear_draft, remove_ids, edits = self._parse_assist(
                result.data
            )
        except Exception as exc:  # noqa: BLE001 - keep the user's message on failure
            logger.exception("Draft assist failed")
            reply = "I could not reach the writing model just now. Your draft is safe — try again."
            title = ""
            clear_draft = False
            remove_ids = []
            edits = []
            draft.error = str(exc)[:300]
        if clear_draft:
            draft.blocks = []
        elif remove_ids:
            drop = set(remove_ids)
            draft.blocks = [
                block for block in draft.blocks if block.blockId not in drop
            ]
        # The model occasionally says it cleared the draft without returning the
        # flag. Trust an explicit clear request so the reply and the document
        # can never disagree.
        if (
            not clear_draft
            and not remove_ids
            and not edits
            and _looks_like_clear(payload.message)
        ):
            draft.blocks = []
        self._apply_edits(draft, edits)
        if title:
            draft.title = title.strip()[:200]
        draft.messages.append(
            DraftMessage(
                messageId=_new_id(),
                role="assistant",
                content=reply,
                createdAt=datetime.now(UTC),
            )
        )
        if draft.status == DraftStatus.empty and draft.blocks:
            draft.status = DraftStatus.ready
        self._persist(owner_uid=owner_uid, draft=draft, status=ProjectStatus.ready)
        return draft

    # ---------------------------------------------------------------- helpers

    async def suggest(
        self, *, owner_uid: str, project_id: str, payload: SuggestDraftRequest
    ) -> list[str]:
        """Return drop-in replacements for a selected span.

        Unlike `assist`, this does not touch the stored draft: the client wraps the
        selection in an inline variant and saves it, so word/sentence alternatives
        stay inside the paragraph instead of becoming whole-block versions.
        """
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        count = payload.count if payload.mode == SuggestMode.alternatives else 1
        user = json.dumps(
            {
                "selection": payload.text,
                "surrounding": payload.context[:2000],
                "mode": payload.mode.value,
                "count": count,
            },
            ensure_ascii=False,
        )
        try:
            completion = await self.llm.complete_json(
                model=self.settings.model_suggest,
                prompt_version=DRAFT_SUGGEST_PROMPT_VERSION,
                system=SUGGEST_SYSTEM,
                user=user,
                schema=SUGGEST_SCHEMA,
            )
            suggestions = [
                str(item).strip()
                for item in (completion.data.get("suggestions") or [])
                if str(item).strip()
            ]
        except Exception:  # noqa: BLE001 - the client falls back to the original
            logger.exception("Draft suggest failed")
            suggestions = []
        return suggestions[:count]

    def _apply_overrides(
        self, brief: DraftBrief, overrides: GenerateDraftRequest
    ) -> DraftBrief:
        patch = {
            key: value
            for key, value in overrides.model_dump(exclude_none=True).items()
        }
        merged = brief.model_copy(update=patch)
        if not merged.topic.strip():
            raise BadRequestError("A draft needs a topic before it can be generated.")
        return merged

    async def _generate_blocks(
        self, brief: DraftBrief, draft: Draft, *, owner_uid: str
    ) -> list[DraftBlock]:
        payload: dict[str, Any] = {"brief": brief.model_dump(mode="json")}
        # RAG: the creator's own past titles/descriptions (their most recently synced channel) as
        # style evidence, retrieved against this brief. Absent when nothing has been synced.
        if self.content is not None:
            creator_context = self.content.build_context_for_user(
                owner_uid,
                query=f"{brief.topic} {brief.instructions}".strip(),
                k=5,
            )
            if creator_context:
                payload["creatorContext"] = creator_context
        user = json.dumps(payload, indent=2, ensure_ascii=False)
        try:
            completion = await self.llm.complete_json(
                model=self.settings.model_writer,
                prompt_version=DRAFT_GENERATE_PROMPT_VERSION,
                system=GENERATE_SYSTEM,
                user=user,
                schema=GENERATE_SCHEMA,
            )
            data = completion.data
            blocks = [
                _make_block(
                    type_=self._block_type(item.get("type")),
                    text=str(item.get("text", "")),
                    label="Draft",
                )
                for item in data.get("blocks", [])
                if str(item.get("text", "")).strip()
            ]
            title = str(data.get("title", "")).strip()
        except Exception:  # noqa: BLE001 - always return a usable draft
            logger.exception("Draft generation failed; using deterministic fallback")
            blocks = _fallback_blocks(brief)
            title = brief.topic.strip()
        if not blocks:
            blocks = _fallback_blocks(brief)
        if title and not draft.title:
            draft.title = title
        return blocks

    def _assist_context(self, draft: Draft, payload: AssistDraftRequest) -> str:
        blocks = [
            {
                "blockId": block.blockId,
                "type": block.type.value,
                "text": strip_html(active_text(block)),
                "versions": len(block.versions),
            }
            for block in draft.blocks
        ]
        context: dict[str, Any] = {
            "brief": draft.brief.model_dump(mode="json"),
            "title": draft.title,
            "blocks": blocks,
            "request": {
                "message": payload.message.strip(),
                "mode": payload.mode.value,
                "targetBlockId": payload.blockId,
            },
        }
        if payload.mode == AssistMode.alternatives:
            context["request"]["instruction"] = (
                "Return 3 distinct alternatives for targetBlockId, each a new version."
            )
        elif payload.mode == AssistMode.continue_draft:
            context["request"]["instruction"] = (
                "Continue the draft by appending new blocks that follow the current ending."
            )
        return json.dumps(context, indent=2, ensure_ascii=False)

    def _parse_assist(
        self, data: dict[str, Any]
    ) -> tuple[str, str, bool, list[str], list[dict[str, Any]]]:
        reply = str(data.get("reply", "")).strip() or "Updated the draft."
        title = str(data.get("title", "")).strip()
        clear_draft = bool(data.get("clearDraft"))
        remove_ids = [
            str(item)
            for item in (data.get("removeBlockIds") or [])
            if str(item).strip()
        ]
        edits = [
            item
            for item in data.get("blocks", [])
            if str(item.get("text", "")).strip()
        ]
        return reply, title, clear_draft, remove_ids, edits

    def _apply_edits(self, draft: Draft, edits: list[dict[str, Any]]) -> None:
        index: dict[str, DraftBlock] = {block.blockId: block for block in draft.blocks}
        for item in edits:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            block_id = str(item.get("blockId", "")).strip()
            label = str(item.get("label", "")).strip() or "Revision"
            target = index.get(block_id) if block_id else None
            if target is None and block_id:
                continue
            if target is None:
                target = _make_block(
                    type_=self._block_type(item.get("type")), text=text, label=label
                )
                draft.blocks.append(target)
                index[target.blockId] = target
                continue
            version = DraftVersion(
                versionId=_new_id(),
                text=text,
                label=label,
                origin="assistant",
                createdAt=datetime.now(UTC),
            )
            target.versions.append(version)
            target.activeVersionId = version.versionId

    def _block_type(self, value: Any) -> DraftBlockType:
        try:
            return DraftBlockType(str(value))
        except ValueError:
            return DraftBlockType.paragraph

    def _persist(self, *, owner_uid: str, draft: Draft, status: Any) -> None:
        now = datetime.now(UTC)
        draft.updatedAt = now
        if draft.createdAt is None:
            draft.createdAt = now
        draft.summary = build_summary(draft)
        stored = draft.model_dump()
        self.client.set_document(draft_path(owner_uid, draft.projectId), stored)
        self.projects.update_draft_summary(
            owner_uid=owner_uid,
            project_id=draft.projectId,
            summary=draft.summary,
            status=status,
        )

    def _to_draft(self, project_id: str, data: dict[str, Any]) -> Draft:
        return Draft(projectId=project_id, **{k: v for k, v in data.items() if k != "projectId"})
