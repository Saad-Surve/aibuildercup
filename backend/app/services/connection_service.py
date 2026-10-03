"""Connected-account lifecycle: OAuth start/callback, token storage, channel sync, revoke.

The creator can connect several Google accounts and several channels; each becomes one
`Connection` document under `users/{uid}/connections/{connectionId}` with the encrypted tokens
in a sibling `connectionSecrets` document. `prompt=select_account` in the authorization URL is
what gives the creator the Gmail account picker.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.connectors.base import ChannelInfo
from app.connectors.youtube import YouTubeConnector
from app.errors import BadRequestError, NotFoundError
from app.schemas.connections import (
    Connection,
    ConnectionPlatform,
    ConnectionStatus,
    OAuthStartRequest,
    OAuthStartResponse,
)
from app.services.firestore_service import (
    FirestoreClient,
    connection_path,
    connection_secret_path,
    connections_collection_path,
    oauth_state_path,
)
from app.services.oauth_service import (
    GoogleOAuthClient,
    OAuthTokenSet,
    build_oauth_client,
    build_pkce_pair,
    generate_state,
)
from app.services.token_cipher import TokenCipher

logger = logging.getLogger(__name__)

#: Only these scopes are recorded on the connection for display; Google's own response is the
#: source of truth for what was actually granted.
_DISPLAY_SCOPES = (
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
)


def _to_connection(connection_id: str, data: dict[str, Any]) -> Connection:
    return Connection(
        connectionId=connection_id,
        platform=ConnectionPlatform(data.get("platform", "youtube")),
        accountType=data.get("accountType", "channel"),
        displayName=data.get("displayName") or "YouTube channel",
        externalAccountId=data.get("externalAccountId", ""),
        externalHandle=data.get("externalHandle"),
        googleAccountEmail=data.get("googleAccountEmail"),
        avatarUrl=data.get("avatarUrl"),
        subscriberCount=data.get("subscriberCount"),
        videoCount=data.get("videoCount"),
        status=ConnectionStatus(data.get("status", ConnectionStatus.connected.value)),
        scopes=list(data.get("scopes") or []),
        lastSyncAt=data.get("lastSyncAt"),
        lastSyncStatus=data.get("lastSyncStatus"),
        lastErrorCode=data.get("lastErrorCode"),
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


class ConnectionService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        cipher: TokenCipher,
        connector_factory: Any | None = None,
        settings: Settings,
    ) -> None:
        self.client = client
        self.cipher = cipher
        self.settings = settings
        self._connector_factory = connector_factory

    # ------------------------------------------------------------------ oauth

    def start_oauth(
        self,
        *,
        owner_uid: str,
        platform: str,
        payload: OAuthStartRequest,
    ) -> OAuthStartResponse:
        if platform != ConnectionPlatform.youtube.value:
            raise BadRequestError(
                "Unsupported platform.", code="UNSUPPORTED_PLATFORM", details={"platform": platform}
            )
        client = self._oauth_client()
        state = generate_state()
        code_verifier, code_challenge = build_pkce_pair()
        now = datetime.now(UTC)
        from datetime import timedelta

        self.client.set_document(
            oauth_state_path(owner_uid, state),
            {
                "ownerUid": owner_uid,
                "state": state,
                "platform": platform,
                "codeVerifier": code_verifier,
                "redirectPath": _safe_redirect_path(payload.redirectPath),
                "createdAt": now,
                "expiresAt": now + timedelta(seconds=self.settings.oauth_state_ttl_seconds),
            },
        )
        return OAuthStartResponse(
            authorizationUrl=client.authorization_url(
                state=state,
                code_challenge=code_challenge,
                login_hint=payload.loginHint,
            ),
            state=state,
        )

    def handle_callback(self, *, state: str, code: str | None, error: str | None) -> str:
        """Finish OAuth and return the browser redirect URL.

        Runs without Firebase auth (Google is the caller), so the signed `state` document is
        the only proof of who started the flow. The state is consumed exactly once.
        """
        found = self._find_state(state)
        if found is None:
            return self._error_redirect(None, "This connection link is no longer valid.")
        owner_uid, state_path, state_data = found
        self.client.delete_document(state_path)
        redirect_path = state_data.get("redirectPath") or "/profile"

        if error:
            return self._error_redirect(redirect_path, f"Google returned an error: {error}")
        if not code:
            return self._error_redirect(
                redirect_path, "Google did not return an authorization code."
            )

        client = self._oauth_client()
        try:
            tokens = client.exchange_code(code=code, code_verifier=state_data["codeVerifier"])
            userinfo = client.userinfo(access_token=tokens.access_token)
            channels = self._connector().list_channels(tokens)
        except Exception as exc:  # noqa: BLE001 - surfaced to the browser
            logger.warning("youtube oauth callback failed", exc_info=True)
            message = getattr(exc, "message", None) or "Connecting YouTube failed."
            return self._error_redirect(redirect_path, str(message))

        if not channels:
            return self._error_redirect(
                redirect_path,
                "That Google account has no YouTube channel. Create a channel first, then retry.",
            )

        connection_ids: list[str] = []
        for channel in channels:
            connection_ids.append(
                self._upsert_connection(owner_uid, channel, tokens, userinfo.email)
            )

        query = f"youtube=connected&connections={','.join(connection_ids)}"
        if userinfo.email:
            query += f"&googleAccount={userinfo.email}"
        return self._web_redirect(redirect_path, query)

    def _find_state(self, state: str) -> tuple[str, str, dict[str, Any]] | None:
        rows = self.client.query_collection_group(
            "oauthStates", filters=[("state", "==", state)], limit=5
        )
        for state_id, data in rows:
            owner_uid = data.get("ownerUid")
            if not owner_uid:
                continue
            expires_at = data.get("expiresAt")
            if isinstance(expires_at, datetime) and expires_at < datetime.now(UTC):
                self.client.delete_document(oauth_state_path(owner_uid, state_id))
                return None
            return owner_uid, oauth_state_path(owner_uid, state_id), data
        return None

    def _upsert_connection(
        self,
        owner_uid: str,
        channel: ChannelInfo,
        tokens: OAuthTokenSet,
        google_email: str | None,
    ) -> str:
        now = datetime.now(UTC)
        existing = self._find_by_channel(owner_uid, channel.channel_id)
        connection_id = existing[0] if existing else uuid4().hex
        secret_path = connection_secret_path(owner_uid, connection_id)
        encrypted = self.cipher.encrypt(tokens.to_storage())
        self.client.set_document(
            secret_path,
            {
                "ownerUid": owner_uid,
                "connectionId": connection_id,
                "platform": ConnectionPlatform.youtube.value,
                "ciphertext": encrypted.ciphertext,
                "keyVersion": encrypted.key_version,
                "updatedAt": now,
            },
        )
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "platform": ConnectionPlatform.youtube.value,
            "accountType": "channel",
            "displayName": channel.title,
            "externalAccountId": channel.channel_id,
            "externalHandle": channel.handle,
            "googleAccountEmail": google_email,
            "avatarUrl": channel.thumbnail_url,
            "subscriberCount": channel.subscriber_count,
            "videoCount": channel.video_count,
            "status": ConnectionStatus.connected.value,
            "scopes": list(tokens.scopes) or list(_DISPLAY_SCOPES),
            "tokenSecretRef": secret_path,
            "tokenKeyVersion": encrypted.key_version,
            "lastSyncAt": existing[1].get("lastSyncAt") if existing else None,
            "lastSyncStatus": "succeeded",
            "lastErrorCode": None,
            "createdAt": existing[1].get("createdAt") if existing else now,
            "updatedAt": now,
        }
        self.client.set_document(connection_path(owner_uid, connection_id), document)
        return connection_id

    def _find_by_channel(
        self, owner_uid: str, channel_id: str
    ) -> tuple[str, dict[str, Any]] | None:
        rows = self.client.query_collection(
            connections_collection_path(owner_uid),
            filters=[("externalAccountId", "==", channel_id)],
            order_by=[],
            limit=5,
            offset=0,
        )
        for connection_id, data in rows:
            if (
                data.get("ownerUid") == owner_uid
                and data.get("platform") == ConnectionPlatform.youtube.value
            ):
                return connection_id, data
        return None

    def _oauth_client(self) -> GoogleOAuthClient:
        return build_oauth_client(self.settings)

    def _connector(self) -> YouTubeConnector:
        if self._connector_factory is not None:
            return self._connector_factory()
        return YouTubeConnector(
            client_id=self.settings.google_oauth_client_id or "",
            client_secret=self.settings.google_oauth_client_secret or "",
        )

    def _web_redirect(self, path: str, query: str) -> str:
        base = self.settings.web_base_url.rstrip("/")
        return f"{base}{path}?{query}"

    def _error_redirect(self, path: str | None, message: str) -> str:
        from urllib.parse import quote

        return self._web_redirect(
            path or "/profile", f"youtube=error&reason={quote(message)}"
        )

    # ------------------------------------------------------------------ CRUD

    def list(self, *, owner_uid: str) -> list[Connection]:
        rows = self.client.query_collection(
            connections_collection_path(owner_uid),
            filters=[],
            order_by=[("createdAt", "DESCENDING")],
            limit=50,
            offset=0,
        )
        return [
            _to_connection(connection_id, data)
            for connection_id, data in rows
            if data.get("ownerUid") == owner_uid
        ]

    def get(self, *, owner_uid: str, connection_id: str) -> Connection:
        return _to_connection(connection_id, self._require(owner_uid, connection_id))

    def delete(self, *, owner_uid: str, connection_id: str) -> None:
        data = self._require(owner_uid, connection_id)
        tokens = self._load_tokens(owner_uid, data)
        if tokens is not None:
            self._oauth_client().revoke(token=tokens.refresh_token or tokens.access_token)
        self.client.delete_document(connection_secret_path(owner_uid, connection_id))
        self.client.delete_document(connection_path(owner_uid, connection_id))

    def sync(self, *, owner_uid: str, connection_id: str) -> Connection:
        data = self._require(owner_uid, connection_id)
        tokens = self.tokens_for_use(owner_uid=owner_uid, connection_id=connection_id)
        channel = self._connector().refresh_channel(tokens, data.get("externalAccountId", ""))
        now = datetime.now(UTC)
        self.client.update_document(
            connection_path(owner_uid, connection_id),
            {
                "displayName": channel.title,
                "externalHandle": channel.handle,
                "avatarUrl": channel.thumbnail_url,
                "subscriberCount": channel.subscriber_count,
                "videoCount": channel.video_count,
                "lastSyncAt": now,
                "lastSyncStatus": "succeeded",
                "status": ConnectionStatus.connected.value,
                "lastErrorCode": None,
                "updatedAt": now,
            },
        )
        return self.get(owner_uid=owner_uid, connection_id=connection_id)

    # ------------------------------------------------------------------ tokens

    def tokens_for_use(self, *, owner_uid: str, connection_id: str) -> OAuthTokenSet:
        """Return a usable token set, refreshing in place when the access token is stale.

        A refresh token that Google rejects marks the connection `needs_reauth` so the UI can
        prompt the creator to reconnect instead of failing every publish.
        """
        data = self._require(owner_uid, connection_id)
        tokens = self._load_tokens(owner_uid, data)
        if tokens is None or not tokens.refresh_token:
            self._mark_needs_reauth(owner_uid, connection_id, "NO_TOKEN")
            raise BadRequestError(
                "This connection needs to be reconnected.",
                code="CONNECTION_NEEDS_REAUTH",
                details={"connectionId": connection_id},
            )
        if not tokens.is_expired():
            return tokens
        try:
            refreshed = self._oauth_client().refresh(refresh_token=tokens.refresh_token)
        except Exception as exc:  # noqa: BLE001
            self._mark_needs_reauth(owner_uid, connection_id, "REFRESH_FAILED")
            raise BadRequestError(
                "Google rejected the connection's token. Reconnect the channel.",
                code="CONNECTION_NEEDS_REAUTH",
                details={"connectionId": connection_id},
            ) from exc
        self._save_tokens(owner_uid, connection_id, refreshed)
        return refreshed

    def _load_tokens(
        self, owner_uid: str, connection: dict[str, Any]
    ) -> OAuthTokenSet | None:
        connection_id = connection.get("connectionId") or _connection_id_from_ref(
            connection.get("tokenSecretRef")
        )
        if not connection_id:
            return None
        secret = self.client.get_document(connection_secret_path(owner_uid, connection_id))
        if not secret or secret.get("ownerUid") != owner_uid:
            return None
        try:
            payload = self.cipher.decrypt(str(secret.get("ciphertext") or ""))
        except Exception:  # noqa: BLE001 - a corrupt secret is treated as absent
            logger.warning("connection %s: token decrypt failed", connection_id, exc_info=True)
            return None
        return OAuthTokenSet.from_storage(payload)

    def _save_tokens(
        self, owner_uid: str, connection_id: str, tokens: OAuthTokenSet
    ) -> None:
        encrypted = self.cipher.encrypt(tokens.to_storage())
        now = datetime.now(UTC)
        self.client.set_document(
            connection_secret_path(owner_uid, connection_id),
            {
                "ownerUid": owner_uid,
                "connectionId": connection_id,
                "platform": ConnectionPlatform.youtube.value,
                "ciphertext": encrypted.ciphertext,
                "keyVersion": encrypted.key_version,
                "updatedAt": now,
            },
        )
        self.client.update_document(
            connection_path(owner_uid, connection_id),
            {"tokenKeyVersion": encrypted.key_version, "updatedAt": now},
        )

    def _mark_needs_reauth(self, owner_uid: str, connection_id: str, code: str) -> None:
        self.client.update_document(
            connection_path(owner_uid, connection_id),
            {
                "status": ConnectionStatus.needs_reauth.value,
                "lastErrorCode": code,
                "updatedAt": datetime.now(UTC),
            },
        )

    def _require(self, owner_uid: str, connection_id: str) -> dict[str, Any]:
        data = self.client.get_document(connection_path(owner_uid, connection_id))
        if data is None or data.get("ownerUid") != owner_uid:
            raise NotFoundError(
                "Connection not found", details={"connectionId": connection_id}
            )
        data.setdefault("connectionId", connection_id)
        return data


def _connection_id_from_ref(ref: Any) -> str | None:
    if not isinstance(ref, str):
        return None
    return ref.rsplit("/", 1)[-1] or None


def _safe_redirect_path(path: str | None) -> str:
    """Only same-origin, absolute paths are allowed, so a crafted state cannot open-redirect."""
    if not path or not path.startswith("/") or path.startswith("//"):
        return "/profile"
    return path
