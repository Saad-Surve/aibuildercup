"""Copy every document and object owned by one user to another.

Used to seed the read-only demo account from a real creator's content. It reproduces the
`users/{source}` Firestore subtree under `users/{dest}` and every Cloud Storage object under
the matching prefix, rewriting `ownerUid` fields and storage paths as it goes.

Credentials that belong to the source human — connected accounts and their encrypted OAuth
tokens — are deliberately *not* copied. The demo can browse; it must not be able to publish
to someone else's channel.

Usage (from `backend/`):

    uv run python scripts/copy_user_content.py --source <uid> --dest <uid> [--replace]

`--replace` first deletes the destination subtree and object prefix, so re-running the copy is
clean rather than additive.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Make `app` importable whether the script is run from `backend/` or elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.cloud import firestore, storage

from app.config import get_settings

#: Subtrees under `users/{uid}` that are private to the human and never copied.
SKIPPED_COLLECTIONS = {"connections", "connectionSecrets", "oauthStates"}

#: Collections whose documents can themselves have subcollections. Recursing only into these
#: avoids a per-leaf `list_collections` round trip across hundreds of transcript segments.
PARENT_COLLECTIONS = {"projects", "transcripts", "analysisRuns", "jobs"}


def _transform(value: Any, source: str, dest: str) -> Any:
    """Recursively rewrite owner ids and storage paths from `source` to `dest`."""
    source_prefix = f"users/{source}/"
    dest_prefix = f"users/{dest}/"
    if isinstance(value, str):
        return value.replace(source_prefix, dest_prefix)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key == "ownerUid" and item == source:
                result[key] = dest
            else:
                result[key] = _transform(item, source, dest)
        return result
    if isinstance(value, list):
        return [_transform(item, source, dest) for item in value]
    return value


def _walk(
    client: firestore.Client, ref: firestore.DocumentReference
) -> Iterator[tuple[firestore.DocumentReference, dict[str, Any]]]:
    for collection in ref.collections():
        if collection.id in SKIPPED_COLLECTIONS:
            continue
        for snapshot in collection.stream():
            yield snapshot.reference, snapshot.to_dict() or {}
            if collection.id in PARENT_COLLECTIONS:
                yield from _walk(client, snapshot.reference)


def _copy_objects(
    client: storage.Client, bucket_name: str, source: str, dest: str
) -> int:
    bucket = client.bucket(bucket_name)
    source_prefix = f"users/{source}/"
    dest_prefix = f"users/{dest}/"
    copied = 0
    for blob in client.list_blobs(bucket, prefix=source_prefix):
        new_name = dest_prefix + blob.name[len(source_prefix):]
        bucket.copy_blob(blob, bucket, new_name=new_name)
        copied += 1
    return copied


def copy_user(source: str, dest: str, *, replace: bool) -> None:
    settings = get_settings()
    client = firestore.Client(project=settings.project_id)
    source_ref = client.collection("users").document(source)
    dest_ref = client.collection("users").document(dest)

    if client.collection("users").document(source).get().exists is False:
        raise SystemExit(f"Source user users/{source} does not exist.")

    if replace:
        print(f"Replacing users/{dest} and its objects…")
        storage_client = storage.Client(project=settings.project_id)
        storage_client.bucket(settings.media_bucket).delete_blobs(
            list(
                storage_client.list_blobs(
                    settings.media_bucket, prefix=f"users/{dest}/"
                )
            )
        )
        client.recursive_delete(dest_ref)

    docs = 0
    for ref, data in _walk(client, source_ref):
        relative = ref.path[len(f"users/{source}/"):]
        dest_doc = client.document(f"users/{dest}/{relative}")
        dest_doc.set(_transform(data, source, dest))
        docs += 1

    # The root user document itself: copy profile/persona/preferences and stamp read-only.
    root = source_ref.get().to_dict() or {}
    root.pop("uid", None)
    root["uid"] = dest
    root["readOnly"] = True
    client.collection("users").document(dest).set(_transform(root, source, dest))

    storage_client = storage.Client(project=settings.project_id)
    objects = _copy_objects(
        storage_client, settings.media_bucket, source, dest
    )

    print(f"Copied {docs} Firestore documents and {objects} objects.")
    print(f"users/{dest}.readOnly = true")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Source user UID")
    parser.add_argument("--dest", required=True, help="Destination (demo) user UID")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete the destination first so the copy is clean.",
    )
    args = parser.parse_args()
    copy_user(args.source, args.dest, replace=args.replace)


if __name__ == "__main__":
    main()
