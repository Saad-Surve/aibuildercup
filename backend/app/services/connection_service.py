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
from app.providers.medium import MediumProvider
from app.providers.reddit import RedditIdentity, RedditOAuthClient
from app.providers.substack import SubstackProvider
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


_PLATFORM_FALLBACK_NAME = {
    ConnectionPlatform.youtube.value: "YouTube channel",
    ConnectionPlatform.medium.value: "Medium profile",
    ConnectionPlatform.substack.value: "Substack publication",
    ConnectionPlatform.reddit.value: "Reddit account",
}


def _to_connection(connection_id: str, data: dict[str, Any]) -> Connection:
    platform = str(data.get("platform", "youtube"))
    return Connection(
        connectionId=connection_id,
        platform=ConnectionPlatform(platform),
        accountType=data.get("accountType", "channel"),
        displayName=data.get("displayName")
        or _PLATFORM_FALLBACK_NAME.get(platform, "Connected account"),
        externalAccountId=data.get("externalAccountId", ""),
        externalHandle=data.get("externalHandle"),
        googleAccountEmail=data.get("googleAccountEmail"),
        uploadsPlaylistId=data.get("uploadsPlaylistId"),
        avatarUrl=data.get("avatarUrl"),
        profileUrl=data.get("profileUrl"),
        subscriberCount=data.get("subscriberCount"),
        videoCount=data.get("videoCount"),
        status=ConnectionStatus(data.get("status", ConnectionStatus.connected.value)),
        scopes=list(data.get("scopes") or []),
        lastSyncAt=data.get("lastSyncAt"),
        lastSyncStatus=data.get("lastSyncStatus"),
        lastErrorCode=data.get("lastErrorCode"),
        contentSyncedAt=data.get("contentSyncedAt"),
        contentItemCount=data.get("contentItemCount"),
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
        if platform not in (
            ConnectionPlatform.youtube.value,
            ConnectionPlatform.reddit.value,
        ):
            raise BadRequestError(
                "Unsupported platform for OAuth.",
                code="UNSUPPORTED_PLATFORM",
                details={"platform": platform},
            )
        state = generate_state()
        now = datetime.now(UTC)
        from datetime import timedelta

        if platform == ConnectionPlatform.reddit.value:
            client = self._reddit_client()
            self.client.set_document(
                oauth_state_path(owner_uid, state),
                {
                    "ownerUid": owner_uid,
                    "state": state,
                    "platform": platform,
                    "codeVerifier": "",
                    "redirectPath": _safe_redirect_path(payload.redirectPath),
                    "createdAt": now,
                    "expiresAt": now
                    + timedelta(seconds=self.settings.oauth_state_ttl_seconds),
                },
            )
            return OAuthStartResponse(
                authorizationUrl=client.authorization_url(state=state),
                state=state,
            )
        oauth = self._oauth_client()
        code_verifier, code_challenge = build_pkce_pair()
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
            authorizationUrl=oauth.authorization_url(
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
            return self._error_redirect(
                None, "youtube", "This connection link is no longer valid."
            )
        owner_uid, state_path, state_data = found
        self.client.delete_document(state_path)
        redirect_path = state_data.get("redirectPath") or "/profile"
        platform = str(state_data.get("platform") or ConnectionPlatform.youtube.value)

        if error:
            return self._error_redirect(
                redirect_path, platform, f"The provider returned an error: {error}"
            )
        if not code:
            return self._error_redirect(
                redirect_path, platform, "The provider did not return an authorization code."
            )

        if platform == ConnectionPlatform.reddit.value:
            return self._finish_reddit_callback(
                owner_uid=owner_uid, redirect_path=redirect_path, code=code
            )
        return self._finish_youtube_callback(
            owner_uid=owner_uid, redirect_path=redirect_path, code=code, state_data=state_data
        )

    def _finish_youtube_callback(
        self,
        *,
        owner_uid: str,
        redirect_path: str,
        code: str,
        state_data: dict[str, Any],
    ) -> str:
        client = self._oauth_client()
        try:
            tokens = client.exchange_code(code=code, code_verifier=state_data["codeVerifier"])
            userinfo = client.userinfo(access_token=tokens.access_token)
            channels = self._connector().list_channels(tokens)
        except Exception as exc:  # noqa: BLE001 - surfaced to the browser
            logger.warning("youtube oauth callback failed", exc_info=True)
            message = getattr(exc, "message", None) or "Connecting YouTube failed."
            return self._error_redirect(redirect_path, "youtube", str(message))

        if not channels:
            return self._error_redirect(
                redirect_path,
                "youtube",
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

    def _finish_reddit_callback(
        self, *, owner_uid: str, redirect_path: str, code: str
    ) -> str:
        try:
            client = self._reddit_client()
            received = client.exchange_code(code=code)
            identity = client.me(received.access_token)
        except Exception as exc:  # noqa: BLE001 - surfaced to the browser
            logger.warning("reddit oauth callback failed", exc_info=True)
            message = getattr(exc, "message", None) or "Connecting Reddit failed."
            return self._error_redirect(redirect_path, "reddit", str(message))
        connection_id = self._upsert_reddit_connection(
            owner_uid, identity, received.access_token, received.refresh_token
        )
        return self._web_redirect(
            redirect_path, f"reddit=connected&connections={connection_id}"
        )

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
        existing = self._find_by_external(
            owner_uid, ConnectionPlatform.youtube.value, channel.channel_id
        )
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
            "uploadsPlaylistId": channel.uploads_playlist_id,
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

    def _load_secret(self, *, owner_uid: str, connection_id: str) -> dict[str, Any] | None:
        """Raw decrypted secret for token/cookie platforms (Medium, Substack)."""
        secret = self.client.get_document(connection_secret_path(owner_uid, connection_id))
        if not secret or secret.get("ownerUid") != owner_uid:
            return None
        try:
            payload = self.cipher.decrypt(str(secret.get("ciphertext") or ""))
        except Exception:  # noqa: BLE001 - a corrupt secret is treated as absent
            logger.warning("connection %s: secret decrypt failed", connection_id, exc_info=True)
            return None
        return payload if isinstance(payload, dict) else None

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

    def _error_redirect(self, path: str | None, platform: str, message: str) -> str:
        from urllib.parse import quote

        return self._web_redirect(
            path or "/profile", f"{platform}=error&reason={quote(message)}"
        )

    # ------------------------------------------------- token/cookie connects

    def connect_medium(self, *, owner_uid: str, token: str) -> Connection:
        """Connect Medium with a legacy integration token (no new tokens exist)."""
        identity = MediumProvider().get_me(token.strip())
        connection_id = self._upsert_text_connection(
            owner_uid,
            platform=ConnectionPlatform.medium.value,
            accountType="profile",
            display_name=identity.name,
            external_account_id=identity.user_id,
            external_handle=f"@{identity.username}" if identity.username else None,
            profile_url=identity.profile_url,
            avatar_url=identity.image_url,
            secret={"authKind": "token", "token": token.strip()},
            scopes=["post"],
        )
        return self.get(owner_uid=owner_uid, connection_id=connection_id)

    def connect_substack(
        self, *, owner_uid: str, sid: str, subdomain: str | None = None
    ) -> Connection:
        """Connect a Substack publication with a browser session cookie.

        The publication is auto-detected — one publication connects straight
        away, several ask the caller to pick — so the user never has to type a
        subdomain.
        """
        provider = SubstackProvider()
        clean_sid = provider.extract_sid(sid)
        profile = provider.get_profile(clean_sid)
        if subdomain and subdomain.strip():
            publication = provider.pick_publication(
                profile, provider.normalize_subdomain(subdomain)
            )
        else:
            publications = provider.list_publications(profile)
            if not publications:
                raise BadRequestError(
                    "This Substack account has no publication.",
                    code="SUBSTACK_NO_PUBLICATION",
                )
            if len(publications) > 1:
                raise BadRequestError(
                    "This Substack account has more than one publication — pick one.",
                    code="SUBSTACK_MULTIPLE_PUBLICATIONS",
                    details={
                        "publications": [
                            {"subdomain": pub.subdomain, "name": pub.name}
                            for pub in publications
                        ]
                    },
                )
            publication = publications[0]
        connection_id = self._upsert_text_connection(
            owner_uid,
            platform=ConnectionPlatform.substack.value,
            accountType="publication",
            display_name=publication.name,
            external_account_id=str(publication.publication_id),
            external_handle=publication.subdomain,
            profile_url=publication.url,
            avatar_url=None,
            secret={
                "authKind": "cookie",
                "sid": clean_sid,
                "subdomain": publication.subdomain,
            },
            scopes=["post"],
        )
        return self.get(owner_uid=owner_uid, connection_id=connection_id)

    def _upsert_text_connection(
        self,
        owner_uid: str,
        *,
        platform: str,
        accountType: str,
        display_name: str,
        external_account_id: str,
        external_handle: str | None,
        profile_url: str | None,
        avatar_url: str | None,
        secret: dict[str, Any],
        scopes: list[str],
    ) -> str:
        now = datetime.now(UTC)
        existing = self._find_by_external(owner_uid, platform, external_account_id)
        connection_id = existing[0] if existing else uuid4().hex
        encrypted = self.cipher.encrypt(secret)
        self.client.set_document(
            connection_secret_path(owner_uid, connection_id),
            {
                "ownerUid": owner_uid,
                "connectionId": connection_id,
                "platform": platform,
                "ciphertext": encrypted.ciphertext,
                "keyVersion": encrypted.key_version,
                "updatedAt": now,
            },
        )
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "platform": platform,
            "accountType": accountType,
            "displayName": display_name,
            "externalAccountId": external_account_id,
            "externalHandle": external_handle,
            "profileUrl": profile_url,
            "avatarUrl": avatar_url,
            "status": ConnectionStatus.connected.value,
            "scopes": scopes,
            "tokenSecretRef": connection_secret_path(owner_uid, connection_id),
            "tokenKeyVersion": encrypted.key_version,
            "lastSyncAt": existing[1].get("lastSyncAt") if existing else None,
            "lastSyncStatus": "succeeded",
            "lastErrorCode": None,
            "createdAt": existing[1].get("createdAt") if existing else now,
            "updatedAt": now,
        }
        self.client.set_document(connection_path(owner_uid, connection_id), document)
        return connection_id

    def _upsert_reddit_connection(
        self,
        owner_uid: str,
        identity: RedditIdentity,
        access_token: str,
        refresh_token: str | None,
    ) -> str:
        from datetime import timedelta

        now = datetime.now(UTC)
        existing = self._find_by_external(
            owner_uid, ConnectionPlatform.reddit.value, identity.account_id
        )
        connection_id = existing[0] if existing else uuid4().hex
        tokens = OAuthTokenSet(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=now + timedelta(seconds=3600),
            scopes=tuple(self.settings.reddit_oauth_scopes),
        )
        encrypted = self.cipher.encrypt(tokens.to_storage())
        self.client.set_document(
            connection_secret_path(owner_uid, connection_id),
            {
                "ownerUid": owner_uid,
                "connectionId": connection_id,
                "platform": ConnectionPlatform.reddit.value,
                "ciphertext": encrypted.ciphertext,
                "keyVersion": encrypted.key_version,
                "updatedAt": now,
            },
        )
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "platform": ConnectionPlatform.reddit.value,
            "accountType": "profile",
            "displayName": f"u/{identity.username}",
            "externalAccountId": identity.account_id,
            "externalHandle": f"u/{identity.username}",
            "profileUrl": identity.profile_url,
            "avatarUrl": identity.avatar_url,
            "status": ConnectionStatus.connected.value,
            "scopes": list(self.settings.reddit_oauth_scopes),
            "tokenSecretRef": connection_secret_path(owner_uid, connection_id),
            "tokenKeyVersion": encrypted.key_version,
            "lastSyncAt": existing[1].get("lastSyncAt") if existing else None,
            "lastSyncStatus": "succeeded",
            "lastErrorCode": None,
            "createdAt": existing[1].get("createdAt") if existing else now,
            "updatedAt": now,
        }
        self.client.set_document(connection_path(owner_uid, connection_id), document)
        return connection_id

    def _find_by_external(
        self, owner_uid: str, platform: str, external_id: str
    ) -> tuple[str, dict[str, Any]] | None:
        rows = self.client.query_collection(
            connections_collection_path(owner_uid),
            filters=[("externalAccountId", "==", external_id)],
            order_by=[],
            limit=5,
            offset=0,
        )
        for connection_id, data in rows:
            if (
                data.get("ownerUid") == owner_uid
                and data.get("platform") == platform
            ):
                return connection_id, data
        return None

    def _reddit_client(self) -> RedditOAuthClient:
        if not self.settings.reddit_oauth_client_id or not self.settings.reddit_oauth_client_secret:
            raise BadRequestError(
                "Reddit OAuth is not configured.",
                code="REDDIT_NOT_CONFIGURED",
            )
        redirect = self.settings.reddit_oauth_redirect_uri or (
            f"{self.settings.api_public_base_url.rstrip('/')}"
            "/api/connections/reddit/oauth/callback"
        )
        return RedditOAuthClient(
            client_id=self.settings.reddit_oauth_client_id,
            client_secret=self.settings.reddit_oauth_client_secret,
            redirect_uri=redirect,
            scopes=tuple(self.settings.reddit_oauth_scopes),
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
        # Only Google offers a server-side revoke. Reddit has no revoke endpoint and
        # Medium/Substack credentials are bearer secrets, so for those deleting the
        # stored secret is the disconnect.
        if data.get("platform") == ConnectionPlatform.youtube.value:
            tokens = self._load_tokens(owner_uid, data)
            if tokens is not None:
                self._oauth_client().revoke(token=tokens.refresh_token or tokens.access_token)
        self.client.delete_document(connection_secret_path(owner_uid, connection_id))
        self.client.delete_document_tree(connection_path(owner_uid, connection_id))

    def revoke_all(self, *, owner_uid: str) -> None:
        """Best-effort revoke of every connected account's token before account deletion.

        Account deletion removes the Firestore tree, which is the only place the encrypted
        tokens live, so the grants must be revoked here or they leak at the provider. Never
        raises: deletion must proceed even if the OAuth client is unconfigured or a provider
        revoke fails.
        """
        try:
            connections = self.list(owner_uid=owner_uid)
        except Exception:  # noqa: BLE001 - a read failure must not block deletion
            logger.warning("revoke_all: could not list connections", exc_info=True)
            return
        if not connections:
            return
        try:
            client = self._oauth_client()
        except Exception:  # noqa: BLE001 - e.g. OAUTH_NOT_CONFIGURED
            logger.warning("revoke_all: OAuth client unavailable; skipping revoke", exc_info=True)
            return
        for connection in connections:
            # Only YouTube grants are revocable server-side; other platforms'
            # secrets die with the Firestore tree.
            if connection.platform != ConnectionPlatform.youtube:
                continue
            try:
                data = self._require(owner_uid, connection.connectionId)
                tokens = self._load_tokens(owner_uid, data)
                if tokens is not None:
                    client.revoke(token=tokens.refresh_token or tokens.access_token)
            except Exception:  # noqa: BLE001 - one failure must not block the rest
                logger.warning(
                    "revoke_all: revoke failed for %s", connection.connectionId, exc_info=True
                )

    def sync(self, *, owner_uid: str, connection_id: str) -> Connection:
        data = self._require(owner_uid, connection_id)
        platform = str(data.get("platform") or ConnectionPlatform.youtube.value)
        if platform != ConnectionPlatform.youtube.value:
            return self._sync_text_connection(owner_uid=owner_uid, connection_id=connection_id)
        tokens = self.tokens_for_use(owner_uid=owner_uid, connection_id=connection_id)
        channel = self._connector().refresh_channel(tokens, data.get("externalAccountId", ""))
        now = datetime.now(UTC)
        self.client.update_document(
            connection_path(owner_uid, connection_id),
            {
                "displayName": channel.title,
                "externalHandle": channel.handle,
                "uploadsPlaylistId": channel.uploads_playlist_id,
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

    def _sync_text_connection(self, *, owner_uid: str, connection_id: str) -> Connection:
        """Re-verify identity for token/cookie/OAuth-profile platforms.

        Refreshes the display name/avatar and flips a dead credential to
        `needs_reauth` so the UI prompts a reconnect instead of failing posts.
        """
        from app.connectors.base import ConnectorError

        data = self._require(owner_uid, connection_id)
        platform = str(data.get("platform"))
        now = datetime.now(UTC)
        try:
            if platform == ConnectionPlatform.medium.value:
                secret = self._load_secret(owner_uid=owner_uid, connection_id=connection_id)
                if not secret or not secret.get("token"):
                    raise BadRequestError("Missing credential.", code="CONNECTION_NEEDS_REAUTH")
                medium_identity = MediumProvider().get_me(str(secret["token"]))
                patch: dict[str, Any] = {
                    "displayName": medium_identity.name,
                    "externalHandle": f"@{medium_identity.username}"
                    if medium_identity.username
                    else None,
                    "profileUrl": medium_identity.profile_url,
                    "avatarUrl": medium_identity.image_url,
                }
            elif platform == ConnectionPlatform.substack.value:
                secret = self._load_secret(owner_uid=owner_uid, connection_id=connection_id)
                if not secret or not secret.get("sid"):
                    raise BadRequestError("Missing credential.", code="CONNECTION_NEEDS_REAUTH")
                provider = SubstackProvider()
                sub = provider.normalize_subdomain(str(secret.get("subdomain") or ""))
                publication = provider.pick_publication(
                    provider.get_profile(str(secret["sid"])), sub
                )
                patch = {
                    "displayName": publication.name,
                    "profileUrl": publication.url,
                }
            elif platform == ConnectionPlatform.reddit.value:
                tokens = self.reddit_tokens_for_use(
                    owner_uid=owner_uid, connection_id=connection_id
                )
                reddit_identity = self._reddit_client().me(tokens.access_token)
                patch = {
                    "displayName": f"u/{reddit_identity.username}",
                    "externalHandle": f"u/{reddit_identity.username}",
                    "profileUrl": reddit_identity.profile_url,
                    "avatarUrl": reddit_identity.avatar_url,
                }
            else:
                raise BadRequestError("Unsupported platform.", code="UNSUPPORTED_PLATFORM")
        except ConnectorError as exc:
            self._mark_needs_reauth(owner_uid, connection_id, exc.code)
            raise BadRequestError(
                "This connection needs to be reconnected.",
                code="CONNECTION_NEEDS_REAUTH",
                details={"connectionId": connection_id},
            ) from exc
        except BadRequestError as exc:
            if exc.code in ("CONNECTION_NEEDS_REAUTH",):
                self._mark_needs_reauth(owner_uid, connection_id, exc.code)
            raise
        patch.update(
            {
                "lastSyncAt": now,
                "lastSyncStatus": "succeeded",
                "status": ConnectionStatus.connected.value,
                "lastErrorCode": None,
                "updatedAt": now,
            }
        )
        self.client.update_document(connection_path(owner_uid, connection_id), patch)
        return self.get(owner_uid=owner_uid, connection_id=connection_id)

    def reddit_tokens_for_use(self, *, owner_uid: str, connection_id: str) -> OAuthTokenSet:
        """Usable Reddit tokens, refreshing in place when the hour is up."""
        from datetime import timedelta

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
            received = self._reddit_client().refresh(refresh_token=tokens.refresh_token)
        except Exception as exc:  # noqa: BLE001
            self._mark_needs_reauth(owner_uid, connection_id, "REFRESH_FAILED")
            raise BadRequestError(
                "Reddit rejected the connection's token. Reconnect the account.",
                code="CONNECTION_NEEDS_REAUTH",
                details={"connectionId": connection_id},
            ) from exc
        refreshed = OAuthTokenSet(
            access_token=received.access_token,
            refresh_token=received.refresh_token or tokens.refresh_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=received.expires_in),
            scopes=tokens.scopes,
            token_type=tokens.token_type,
        )
        self._save_tokens(
            owner_uid, connection_id, refreshed, platform=ConnectionPlatform.reddit.value
        )
        return refreshed

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
        self,
        owner_uid: str,
        connection_id: str,
        tokens: OAuthTokenSet,
        platform: str = ConnectionPlatform.youtube.value,
    ) -> None:
        encrypted = self.cipher.encrypt(tokens.to_storage())
        now = datetime.now(UTC)
        self.client.set_document(
            connection_secret_path(owner_uid, connection_id),
            {
                "ownerUid": owner_uid,
                "connectionId": connection_id,
                "platform": platform,
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
