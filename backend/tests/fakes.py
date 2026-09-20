"""In-memory `FirestoreClient` for unit tests. Mirrors the narrow protocol only."""

from typing import Any


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


class StubLlmProvider:
    """Minimal `LlmProvider` returning a canned response (or raising)."""

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response or {"markdown": "# Stub persona\n"}
        self.calls: list[dict[str, Any]] = []

    async def complete_json(
        self,
        *,
        model: str,
        prompt_version: str,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append({"model": model, "promptVersion": prompt_version, "user": user})
        return self.response
