from dataclasses import dataclass

from fastapi import Header, HTTPException

from app.auth.firebase import verify_id_token


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: str | None


async def current_user(authorization: str = Header(default="")) -> AuthenticatedUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = verify_id_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return AuthenticatedUser(uid=decoded["uid"], email=decoded.get("email"))
