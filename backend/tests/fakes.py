"""In-memory `FirestoreClient` for unit tests. Mirrors the narrow protocol only."""

from typing import Any

from app.providers.base import LlmCompletion, LlmUsage


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def get_document(self, path: str) -> dict[str, Any] | None:
        data = self.docs.get(path)
        return dict(data) if data is not None else None

    def set_document(self, path: str, data: dict[str, Any]) -> None:
        self.docs[path] = dict(data)

    def update_document(self, path: str, data: dict[str, Any]) -> None:
        if path not in self.docs:
            raise KeyError(path)
        self.docs[path].update(data)

    def delete_document(self, path: str) -> None:
        self.docs.pop(path, None)

    def delete_document_tree(self, path: str) -> None:
        prefix = path + "/"
        for key in [key for key in self.docs if key == path or key.startswith(prefix)]:
            del self.docs[key]

    def query_collection(
        self,
        collection_path: str,
        *,
        filters: list[tuple[str, str, Any]],
        order_by: list[tuple[str, str]],
        limit: int,
        offset: int,
    ) -> list[tuple[str, dict[str, Any]]]:
        prefix = collection_path + "/"
        rows: list[tuple[str, dict[str, Any]]] = []
        for path, data in self.docs.items():
            if not path.startswith(prefix):
                continue
            rest = path[len(prefix) :]
            if "/" in rest or not self._matches(data, filters):
                continue
            rows.append((rest, dict(data)))
        for field, direction in reversed(order_by):
            rows.sort(
                key=lambda row: row[1].get(field),
                reverse=direction.upper() == "DESCENDING",
            )
        return rows[offset : offset + limit]

    def query_collection_group(
        self,
        collection_id: str,
        *,
        filters: list[tuple[str, str, Any]],
        limit: int,
    ) -> list[tuple[str, dict[str, Any]]]:
        marker = f"/{collection_id}/"
        rows: list[tuple[str, dict[str, Any]]] = []
        for path, data in self.docs.items():
            if marker not in path:
                continue
            doc_id = path.rsplit("/", 1)[-1]
            if not self._matches(data, filters):
                continue
            rows.append((doc_id, dict(data)))
        return rows[:limit]

    @staticmethod
    def _matches(data: dict[str, Any], filters: list[tuple[str, str, Any]]) -> bool:
        for field, op, value in filters:
            if op == "==" and data.get(field) != value:
                return False
        return True


class FakeStorageClient:
    """In-memory `StorageClient` for unit tests."""

    def __init__(self) -> None:
        self.objects: dict[str, str] = {}
        self.content_types: dict[str, str] = {}

    def upload_text(
        self, path: str, text: str, *, content_type: str = "text/markdown"
    ) -> None:
        self.objects[path] = text

    def download_text(self, path: str) -> str:
        if path not in self.objects:
            raise KeyError(path)
        return self.objects[path]

    def object_exists(self, path: str) -> bool:
        return path in self.objects

    def signed_download_url(self, path: str, *, expires_seconds: int = 900) -> str:
        return f"https://storage.example/{path}?expires={expires_seconds}"

    def signed_upload_url(
        self, path: str, *, content_type: str, expires_seconds: int = 900
    ) -> str:
        self.content_types[path] = content_type
        return f"https://storage.example/upload/{path}?expires={expires_seconds}"

    def delete_prefix(self, prefix: str) -> int:
        keys = [key for key in self.objects if key.startswith(prefix)]
        for key in keys:
            del self.objects[key]
        return len(keys)


class StubLlmProvider:
    """Minimal `LlmProvider` returning a canned response (or raising)."""

    def __init__(
        self,
        response: dict[str, Any] | None = None,
        *,
        error: Exception | None = None,
        usage: LlmUsage | None = None,
    ) -> None:
        self.response = response or {"markdown": "# Stub persona\n"}
        self.error = error
        self.usage = usage or LlmUsage(input_tokens=10, output_tokens=5)
        self.calls: list[dict[str, Any]] = []

    async def complete_json(
        self,
        *,
        model: str,
        prompt_version: str,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> LlmCompletion:
        self.calls.append(
            {
                "model": model,
                "promptVersion": prompt_version,
                "system": system,
                "user": user,
                "schema": schema,
            }
        )
        if self.error is not None:
            raise self.error
        return LlmCompletion(data=self.response, usage=self.usage)


class FakePubSubClient:
    """Records publishes instead of touching the network."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    def publish(self, *, topic: str, event: dict[str, Any]) -> str:
        self.published.append((topic, event))
        return f"msg-{len(self.published)}"
