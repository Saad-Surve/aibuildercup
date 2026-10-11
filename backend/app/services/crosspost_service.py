"""Cross-post a written piece to a connected text platform.

Unlike the YouTube publish pipeline this is synchronous: Medium, Substack, and
Reddit text posts complete in one API call, so there is no worker or job — the
response carries the live URL (or the draft dashboard URL). Nothing is
persisted; ownership is checked against the project and the connection.

Feature code never touches a platform SDK/HTTP API; all calls go through the
providers in `app/providers/`.
"""

from typing import Any

from app.connectors.base import ConnectorError
from app.errors import BadRequestError, ConflictError
from app.providers.medium import MediumProvider
from app.providers.reddit import RedditOAuthClient
from app.providers.substack import SubstackProvider
from app.schemas.connections import (
    ConnectionPlatform,
    ConnectionStatus,
    CrosspostRequest,
    CrosspostResult,
)
from app.services.connection_service import ConnectionService
from app.services.project_service import ProjectService

_MEDIUM_STATUSES = ("draft", "public", "unlisted")
_SUBSTACK_MODES = ("draft", "publish", "schedule")
_SUBSTACK_AUDIENCES = ("everyone", "subscribers_only", "paid_subscribers_only")


class CrosspostService:
    def __init__(
        self,
        *,
        connections: ConnectionService,
        projects: ProjectService,
    ) -> None:
        self.connections = connections
        self.projects = projects

    def post(
        self, *, owner_uid: str, project_id: str, payload: CrosspostRequest
    ) -> CrosspostResult:
        project = self.projects.get(owner_uid=owner_uid, project_id=project_id)
        connection = self.connections.get(
            owner_uid=owner_uid, connection_id=payload.connectionId
        )
        if connection.platform.value != payload.platform:
            raise BadRequestError(
                "That connection belongs to a different platform.",
                code="CROSSPOST_PLATFORM_MISMATCH",
                details={
                    "connectionId": payload.connectionId,
                    "platform": payload.platform,
                },
            )
        if connection.status != ConnectionStatus.connected:
            raise ConflictError(
                "Reconnect this account before posting.",
                code="CONNECTION_NEEDS_REAUTH",
                details={"connectionId": payload.connectionId},
            )
        title = payload.title.strip()
        body = payload.body.strip()
        if not title or not body:
            raise BadRequestError(
                "A crosspost needs a title and a body.",
                code="CROSSPOST_EMPTY",
            )
        options = payload.options or {}
        try:
            if payload.platform == ConnectionPlatform.medium.value:
                return self._post_medium(owner_uid, connection.connectionId, title, body, options)
            if payload.platform == ConnectionPlatform.substack.value:
                return self._post_substack(
                    owner_uid, connection.connectionId, title, body, options
                )
            if payload.platform == ConnectionPlatform.reddit.value:
                return self._post_reddit(
                    owner_uid,
                    connection.connectionId,
                    connection.externalHandle,
                    project.projectId,
                    title,
                    body,
                    options,
                )
        except ConnectorError as exc:
            if exc.code in (
                "MEDIUM_UNAUTHORIZED",
                "SUBSTACK_UNAUTHORIZED",
                "REDDIT_UNAUTHORIZED",
            ):
                self.connections._mark_needs_reauth(
                    owner_uid, connection.connectionId, exc.code
                )
                raise BadRequestError(
                    "This connection needs to be reconnected.",
                    code="CONNECTION_NEEDS_REAUTH",
                    details={"connectionId": connection.connectionId},
                ) from exc
            raise BadRequestError(
                exc.message, code=exc.code, details={"connectionId": connection.connectionId}
            ) from exc
        raise BadRequestError(
            "Unsupported platform for crossposting.",
            code="UNSUPPORTED_PLATFORM",
            details={"platform": payload.platform},
        )

    # ------------------------------------------------------------------ medium

    def _post_medium(
        self,
        owner_uid: str,
        connection_id: str,
        title: str,
        body: str,
        options: dict[str, Any],
    ) -> CrosspostResult:
        connection = self.connections.get(owner_uid=owner_uid, connection_id=connection_id)
        secret = self.connections._load_secret(
            owner_uid=owner_uid, connection_id=connection_id
        )
        token = (secret or {}).get("token")
        if not token:
            raise BadRequestError(
                "This connection needs to be reconnected.",
                code="CONNECTION_NEEDS_REAUTH",
                details={"connectionId": connection_id},
            )
        publish_status = str(options.get("publishStatus") or "draft")
        if publish_status not in _MEDIUM_STATUSES:
            raise BadRequestError(
                "Medium publishStatus must be draft, public, or unlisted.",
                code="CROSSPOST_BAD_OPTION",
                details={"publishStatus": publish_status},
            )
        if len(title) > 255:
            raise BadRequestError(
                "Medium titles are limited to 255 characters.",
                code="CROSSPOST_TOO_LONG",
            )
        post = MediumProvider().create_post(
            str(token),
            author_id=connection.externalAccountId,
            title=title,
            content=body,
            content_format="markdown",
            publish_status=publish_status,
            canonical_url=options.get("canonicalUrl"),
            tags=options.get("tags") if isinstance(options.get("tags"), list) else None,
        )
        return CrosspostResult(
            platform=ConnectionPlatform.medium.value,
            connectionId=connection_id,
            externalId=post.post_id,
            url=post.url,
            status="draft" if publish_status == "draft" else "published",
            title=title,
        )

    # ---------------------------------------------------------------- substack

    def _post_substack(
        self,
        owner_uid: str,
        connection_id: str,
        title: str,
        body: str,
        options: dict[str, Any],
    ) -> CrosspostResult:
        secret = self.connections._load_secret(
            owner_uid=owner_uid, connection_id=connection_id
        )
        sid = (secret or {}).get("sid")
        subdomain = (secret or {}).get("subdomain")
        if not sid or not subdomain:
            raise BadRequestError(
                "This connection needs to be reconnected.",
                code="CONNECTION_NEEDS_REAUTH",
                details={"connectionId": connection_id},
            )
        mode = str(options.get("mode") or "draft")
        if mode not in _SUBSTACK_MODES:
            raise BadRequestError(
                "Substack mode must be draft, publish, or schedule.",
                code="CROSSPOST_BAD_OPTION",
                details={"mode": mode},
            )
        audience = str(options.get("audience") or "everyone")
        if audience not in _SUBSTACK_AUDIENCES:
            raise BadRequestError(
                "Substack audience must be everyone, subscribers_only, or paid_subscribers_only.",
                code="CROSSPOST_BAD_OPTION",
                details={"audience": audience},
            )
        schedule_at = options.get("scheduleAt")
        if mode == "schedule" and not schedule_at:
            raise BadRequestError(
                "Schedule mode needs an ISO-8601 scheduleAt time.",
                code="CROSSPOST_BAD_OPTION",
            )
        provider = SubstackProvider()
        draft = provider.create_draft(
            str(sid),
            subdomain=str(subdomain),
            title=title,
            body_markdown=body,
            subtitle=str(options.get("subtitle") or ""),
            audience=audience,
            schedule_at=str(schedule_at) if schedule_at else None,
        )
        if mode == "draft" or (mode == "schedule" and schedule_at):
            return CrosspostResult(
                platform=ConnectionPlatform.substack.value,
                connectionId=connection_id,
                externalId=str(draft.draft_id),
                url=draft.dashboard_url,
                status="draft" if mode == "draft" else "scheduled",
                title=title,
            )
        send = options.get("send", True)
        post_url = provider.publish_draft(
            str(sid),
            subdomain=str(subdomain),
            draft_id=draft.draft_id,
            send=bool(send),
        )
        return CrosspostResult(
            platform=ConnectionPlatform.substack.value,
            connectionId=connection_id,
            externalId=str(draft.draft_id),
            url=post_url or draft.dashboard_url,
            status="published",
            title=title,
        )

    # ------------------------------------------------------------------ reddit

    def _post_reddit(
        self,
        owner_uid: str,
        connection_id: str,
        external_handle: str | None,
        project_id: str,
        title: str,
        body: str,
        options: dict[str, Any],
    ) -> CrosspostResult:
        del project_id  # ownership already checked; Reddit needs no project state.
        tokens = self.connections.reddit_tokens_for_use(
            owner_uid=owner_uid, connection_id=connection_id
        )
        subreddit = str(options.get("subreddit") or "").strip()
        if not subreddit:
            handle = (external_handle or "").removeprefix("u/").strip()
            if not handle:
                raise BadRequestError(
                    "Pick a subreddit, or reconnect so your profile is known.",
                    code="CROSSPOST_BAD_OPTION",
                )
            subreddit = f"u_{handle}"
        subreddit = subreddit.removeprefix("r/").removeprefix("u/")
        if len(title) > 300:
            raise BadRequestError(
                "Reddit titles are limited to 300 characters.",
                code="CROSSPOST_TOO_LONG",
            )
        if len(body) > 40000:
            raise BadRequestError(
                "Reddit text posts are limited to 40,000 characters.",
                code="CROSSPOST_TOO_LONG",
            )
        kind = str(options.get("kind") or "self")
        post = RedditOAuthClient.api().submit(
            tokens.access_token,
            subreddit=subreddit,
            title=title,
            kind=kind,
            text=body,
            url=options.get("url"),
            send_replies=bool(options.get("sendReplies", True)),
            nsfw=bool(options.get("nsfw", False)),
            spoiler=bool(options.get("spoiler", False)),
        )
        return CrosspostResult(
            platform=ConnectionPlatform.reddit.value,
            connectionId=connection_id,
            externalId=post.thing_id,
            url=post.url,
            status="published",
            title=title,
        )
