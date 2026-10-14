"""Calibrate a position baseline, without retraining the replay/content model or using Gemini."""

import logging
import math
from bisect import bisect_left
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from statistics import fmean, pstdev
from typing import Any, Literal

from app.config import Settings
from app.errors import AppError, BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.providers.base import ChannelRetention, YouTubeRetentionProvider
from app.providers.youtube_analytics import ANALYTICS_SCOPE, DEADLINE_SECONDS
from app.schemas.analysis import Finding, InterestCurve, InterestMoment, Severity
from app.schemas.interest_calibration import (
    CreatorInterestBucket,
    CreatorInterestCalibration,
    InterestBaselineSource,
)
from app.services.connection_service import ConnectionService
from app.services.firestore_service import FirestoreClient
from app.services.interest import CurvePoint, _moments, _smooth, load_model, transcript_features
from app.services.paths import connection_path, user_path

logger = logging.getLogger(__name__)
_SHAPE_POSITIONS = tuple((i + 0.5) / 100 for i in range(100))
_PRIOR_VIDEOS = 10


def _state_path(uid: str, connection_id: str) -> str:
    return f"{connection_path(uid, connection_id)}/interestCalibration/current"


def _active_path(uid: str) -> str:
    return f"{user_path(uid)}/interestCalibration/current"


def _interpolate(xs: Sequence[float], ys: Sequence[float], x: float) -> float:
    i = bisect_left(xs, x)
    if i == 0:
        return ys[0]
    if i >= len(xs):
        return ys[-1]
    fraction = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
    return ys[i - 1] + fraction * (ys[i] - ys[i - 1])


def fit_position_heads(retention: ChannelRetention) -> tuple[dict[str, Any], int, int]:
    """Normalize each retention curve to the replay model's within-video z-score units.

    This aligns shapes, not labels: retention and replay remain different behaviours.
    Views cap at one video equivalent, preventing one viral upload from dominating.
    """
    buckets: dict[str, list[tuple[list[float], int, float]]] = {"short": [], "long": []}
    for video in retention.videos[:40]:
        pairs = sorted(dict(video.points).items())
        if (
            video.views < 100
            or video.duration_seconds < 30
            or len(pairs) < 90
            or pairs[0][0] > 0.011
            or pairs[-1][0] < 0.989
        ):
            continue
        xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
        if (
            any(not math.isfinite(v) or v < 0 for v in xs + ys)
            or xs[-1] > 1
            or max(b - a for a, b in zip(xs, xs[1:], strict=False)) > 0.025
        ):
            continue
        values = [_interpolate(xs, ys, x) for x in _SHAPE_POSITIONS]
        std, mean = pstdev(values), fmean(values)
        if std < 1e-6:
            continue
        shape = [(v - mean) / std for v in values]
        bucket = "short" if video.duration_seconds <= 180 else "long"
        buckets[bucket].append((shape, video.views, min(1.0, video.views / 1000)))
    heads: dict[str, Any] = {}
    videos = views = 0
    for bucket, samples in buckets.items():
        videos += len(samples)
        views += sum(v for _, v, _ in samples)
        if len(samples) < 3:
            continue
        weight = sum(w for _, _, w in samples)
        shape = [sum(s[i] * w for s, _, w in samples) / weight for i in range(100)]
        heads[bucket] = {
            "shape": [round(v, 6) for v in shape],
            "videos": len(samples),
            "views": sum(v for _, v, _ in samples),
            "creatorWeight": weight / (weight + _PRIOR_VIDEOS),
        }
    return heads, videos, views


def _load_active(client: FirestoreClient, uid: str) -> dict[str, Any] | None:
    pointer = client.get_document(_active_path(uid))
    if not pointer or pointer.get("ownerUid") != uid:
        return None
    connection_id = str(pointer.get("connectionId") or "")
    if not connection_id:
        return None
    connection = client.get_document(connection_path(uid, connection_id))
    if not connection or connection.get("ownerUid") != uid:
        return {"status": "failed", "reason": "The calibrated channel is disconnected."}
    data = client.get_document(_state_path(uid, connection_id))
    if not data or data.get("ownerUid") != uid:
        return None
    if connection.get("platform") != "youtube" or connection.get("status") != "connected":
        return {**data, "status": "failed", "reason": "Reconnect the calibrated YouTube channel."}
    if connection.get("externalAccountId") != data.get("channelId"):
        return {"status": "failed", "reason": "The connected channel identity has changed."}
    if data.get("status") == "calibrating":
        attempted = data.get("attemptedAt")
        if (
            isinstance(attempted, datetime)
            and (datetime.now(UTC) - attempted).total_seconds() > DEADLINE_SECONDS + 60
        ):
            return {
                **data,
                "status": "failed",
                "reason": "Calibration was interrupted. Try again after the cooldown.",
            }
    return data


class InterestCalibrationService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        connections: ConnectionService,
        provider: YouTubeRetentionProvider,
        settings: Settings,
    ) -> None:
        self.client = client
        self.connections = connections
        self.provider = provider
        self.settings = settings

    def get(self, *, owner_uid: str) -> CreatorInterestCalibration:
        data = _load_active(self.client, owner_uid)
        return CreatorInterestCalibration.model_validate(data or {"status": "not_started"})

    def calibrate(self, *, owner_uid: str, connection_id: str) -> CreatorInterestCalibration:
        if owner_uid in self.settings.read_only_user_uids:
            raise ForbiddenError(
                "The shared demo is read-only. Sign in with your own account "
                "to calibrate to your channel.",
                code="READ_ONLY_USER",
            )
        connection = self.connections.get(owner_uid=owner_uid, connection_id=connection_id)
        if connection.platform != "youtube" or connection.status != "connected":
            raise BadRequestError("Connect a YouTube channel before calibrating.")
        if ANALYTICS_SCOPE not in connection.scopes:
            raise BadRequestError(
                "Reconnect YouTube and grant YouTube Analytics access.",
                code="ANALYTICS_SCOPE_REQUIRED",
            )
        if not connection.uploadsPlaylistId or not connection.externalAccountId:
            raise BadRequestError("Sync or reconnect this YouTube channel first.")
        now = datetime.now(UTC)
        next_allowed = now + timedelta(hours=24)
        reservation = f"{user_path(owner_uid)}/interestCalibrationAttempts/current"
        if not self.client.reserve_owned_cooldown(
            reservation,
            owner_uid,
            {
                "ownerUid": owner_uid,
                "connectionId": connection_id,
                "attemptedAt": now,
                "nextAllowedAt": next_allowed,
            },
            now,
        ):
            previous = self.client.get_document(reservation)
            if previous and previous.get("ownerUid") != owner_uid:
                raise NotFoundError("Calibration reservation not found.")
            retry_at = (previous or {}).get("nextAllowedAt")
            raise ConflictError(
                "Channel calibration is available once every 24 hours, or the account "
                "is being removed.",
                code="CALIBRATION_COOLDOWN",
                details={"nextAllowedAt": retry_at.isoformat()}
                if isinstance(retry_at, datetime)
                else {},
            )
        end = now.date() - timedelta(days=3)
        start = end - timedelta(days=364)
        state = CreatorInterestCalibration(
            status="calibrating",
            connectionId=connection_id,
            channelId=connection.externalAccountId,
            channelName=connection.displayName,
            attemptedAt=now,
            nextAllowedAt=next_allowed,
            startDate=start.isoformat(),
            endDate=end.isoformat(),
        )
        self._save(owner_uid, connection_id, state, {})
        if not self.client.set_owned_child(
            user_path(owner_uid),
            _active_path(owner_uid),
            owner_uid,
            {"ownerUid": owner_uid, "connectionId": connection_id},
        ):
            raise ConflictError("The account was removed during calibration.")
        heads: dict[str, Any] = {}
        try:
            tokens = self.connections.tokens_for_use(
                owner_uid=owner_uid, connection_id=connection_id
            )
            if ANALYTICS_SCOPE not in tokens.scopes:
                raise BadRequestError("Reconnect YouTube and grant Analytics access.")
            retention = self.provider.collect(
                access_token=tokens.access_token,
                channel_id=connection.externalAccountId,
                uploads_playlist_id=connection.uploadsPlaylistId,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
            state.apiRequests = retention.api_requests
            heads, videos, views = fit_position_heads(retention)
            state.scannedVideos = retention.scanned_videos
            state.videos, state.views = videos, views
            state.buckets = [
                CreatorInterestBucket.model_validate({"bucket": b, **h}) for b, h in heads.items()
            ]
            state.status = "ready" if heads else "insufficient_data"
            state.calibratedAt = datetime.now(UTC) if heads else None
            state.reason = (
                None
                if heads
                else (
                    "Not enough data: need three videos in the same duration bucket (up to three "
                    "minutes, or longer), each with at least 100 views in the past year and a "
                    "complete, non-flat retention report. YouTube can withhold low-traffic data."
                )
            )
        except AppError as exc:
            state.status, state.reason = "failed", exc.message
            state.apiRequests = int(exc.details.get("apiRequests", 0))
        except Exception:  # noqa: BLE001 - persist a bounded failure, never leak credentials
            logger.warning("channel calibration failed", exc_info=True)
            state.status, state.reason = (
                "failed",
                "Calibration could not be completed. Try again after the cooldown.",
            )
        self._save(owner_uid, connection_id, state, heads)
        return state

    def _save(
        self, uid: str, connection_id: str, state: CreatorInterestCalibration, heads: dict[str, Any]
    ) -> None:
        if not self.client.set_owned_child(
            connection_path(uid, connection_id),
            _state_path(uid, connection_id),
            uid,
            {"ownerUid": uid, **state.model_dump(mode="python"), "heads": heads},
        ):
            raise ConflictError("The account or channel was removed during calibration.")


def apply_creator_baseline(
    client: FirestoreClient,
    *,
    owner_uid: str,
    curve: InterestCurve,
) -> InterestCurve:
    """Change only the baseline and lift selection in memory; saved runs remain reproducible."""
    data = _load_active(client, owner_uid)
    source = InterestBaselineSource(reason="Using the generic drop-off shape.")

    def generic(reason: str) -> InterestCurve:
        return curve.model_copy(
            update={"baselineSource": source.model_copy(update={"reason": reason})}
        )

    if not data or data.get("status") != "ready":
        return generic(str((data or {}).get("reason") or "Using the generic drop-off shape."))
    bucket: Literal["short", "long"] = "short" if curve.durationMs <= 180_000 else "long"
    head = (data.get("heads") or {}).get(bucket)
    if not head:
        return generic("Not enough channel retention data for this video's duration bucket.")
    model = load_model()
    if (
        not model
        or curve.modelVersion != model.version
        or not curve.calibration
        or curve.calibration.trainedAt != model.metrics.get("trainedAt")
    ):
        return generic("This saved run uses an older model. Re-review to use channel calibration.")
    points = curve.points
    rows = transcript_features([], curve.durationMs)
    if not points or len(points) != len(rows):
        return generic("This saved curve has no compatible position baseline.")
    expected = _smooth([model.position.predict(row) for row in rows])
    # Recover the old common min/max scale using all baseline points. Quantization of
    # saved values is <=0.00005; reject anything that isn't the pinned generic head.
    baselines = [p.baseline for p in points]
    mean_b, mean_e = fmean(baselines), fmean(expected)
    variance = sum((b - mean_b) ** 2 for b in baselines)
    if variance < 1e-8:
        return generic("This saved curve has no recoverable position scale.")
    span = (
        sum((b - mean_b) * (e - mean_e) for b, e in zip(baselines, expected, strict=True))
        / variance
    )
    lo = mean_e - span * mean_b
    if (
        span <= 1e-8
        or max(abs(lo + span * b - e) for b, e in zip(baselines, expected, strict=True)) > 0.001
    ):
        return generic(
            "This saved curve's baseline differs from the bundled model. Re-review first."
        )
    shape, weight = head["shape"], float(head["creatorWeight"])
    creator = _smooth(
        [
            _interpolate(_SHAPE_POSITIONS, shape, (p.startMs + p.endMs) / 2 / curve.durationMs)
            for p in points
        ]
    )
    replacement = [(1 - weight) * e + weight * c for e, c in zip(expected, creator, strict=True)]
    predicted = [lo + span * p.value for p in points]
    lower, upper = min(predicted + replacement), max(predicted + replacement)
    width = upper - lower
    if width <= 1e-8:
        return generic("This curve is flat; using the generic baseline.")
    updated = [
        p.model_copy(
            update={
                "value": round((v - lower) / width, 4),
                "baseline": round((b - lower) / width, 4),
            }
        )
        for p, v, b in zip(points, predicted, replacement, strict=True)
    ]
    candidates = [
        CurvePoint(
            start_ms=p.startMs,
            end_ms=p.endMs,
            value=p.value,
            baseline=p.baseline,
            lift=v - b,
            drivers_up=tuple(p.driversUp),
            drivers_down=tuple(p.driversDown),
            signals=p.signals,
        )
        for p, v, b in zip(updated, predicted, replacement, strict=True)
    ]

    def moments(kind: str) -> list[InterestMoment]:
        if curve.featureSource != "transcript+gemini":
            return []
        return [
            InterestMoment(
                kind="peak" if m.kind == "peak" else "dip",
                startMs=m.start_ms,
                endMs=m.end_ms,
                value=m.value,
                drivers=list(m.drivers),
            )
            for m in _moments(candidates, kind=kind)
        ]

    source = InterestBaselineSource(
        source="creator",
        connectionId=data["connectionId"],
        channelName=data["channelName"],
        calibratedAt=data["calibratedAt"],
        videos=head["videos"],
        views=head["views"],
        creatorWeight=weight,
        bucket=bucket,
    )
    return curve.model_copy(
        update={
            "points": updated,
            "peaks": moments("peak"),
            "dips": moments("dip"),
            "baselineSource": source,
        }
    )


def link_calibrated_moments(curve: InterestCurve, findings: Sequence[Finding]) -> InterestCurve:
    ranks = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}

    def link(moment: InterestMoment) -> InterestMoment:
        hits = [
            f
            for f in findings
            if f.startMs < moment.endMs
            and f.endMs > moment.startMs
            and (moment.kind == "peak" or f.severity is not Severity.none)
        ]
        hits.sort(key=lambda f: (-ranks[f.severity.value], f.startMs))
        return moment.model_copy(update={"findingIds": [f.findingId for f in hits[:6]]})

    return curve.model_copy(
        update={"peaks": [link(m) for m in curve.peaks], "dips": [link(m) for m in curve.dips]}
    )
