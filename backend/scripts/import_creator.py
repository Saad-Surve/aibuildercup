"""Operator-only folder import. Validation is local; --apply uses live ADC services."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.creator_import_service import (
    CreatorImportService,
    import_path,
    prepare_import,
)
from app.services.firestore_service import get_firestore_client
from app.services.storage_service import get_storage_client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate a folder without cloud access")
    validate.add_argument("folder", type=Path)
    load = commands.add_parser("import", help="Import/activate a folder for an existing user")
    load.add_argument("folder", type=Path)
    load.add_argument("--uid", required=True)
    load.add_argument("--apply", action="store_true", help="Write to live Firestore/Storage")
    remove = commands.add_parser("remove", help="Delete an imported bundle and its objects")
    remove.add_argument("--uid", required=True)
    remove.add_argument("--bundle-id", required=True)
    remove.add_argument("--apply", action="store_true", help="Delete from live Firestore/Storage")
    args = parser.parse_args()
    try:
        if args.command == "remove":
            path = import_path(args.uid, args.bundle_id)
            if args.apply:
                CreatorImportService(get_firestore_client(), storage=get_storage_client()).remove(
                    args.uid, args.bundle_id
                )
            print(json.dumps({"path": path, "removed": args.apply, "dryRun": not args.apply}))
            return
        prepared = prepare_import(args.folder)
        result = {"dryRun": True, **prepared.summary()}
        if args.command == "import":
            import_path(args.uid, prepared.manifest.bundleId)  # Validate UID before cloud access.
            result["uid"] = args.uid
            if args.apply:
                result = CreatorImportService(
                    get_firestore_client(), storage=get_storage_client()
                ).apply(args.uid, prepared)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Import failed: {exc}\n")


if __name__ == "__main__":
    main()
