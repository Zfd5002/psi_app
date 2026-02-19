from __future__ import annotations

import argparse
from pathlib import Path

from psi.core.db import SessionLocal, ensure_schema
from psi.core.storage import StorageConfig, ensure_storage, save_upload, link_file


def main() -> int:
    ap = argparse.ArgumentParser(description="Import a local file into PSI's file registry and link to an entity.")
    ap.add_argument("--path", required=True, help="Path to the file to import")
    ap.add_argument("--entity-type", required=True, help="Entity type string (e.g., DataRecord, Molecule, Batch)")
    ap.add_argument("--entity-id", required=True, type=int, help="Entity id")
    ap.add_argument("--role", default="raw_input", help="Link role (raw_input, processed_output, report, plot, protocol, other)")
    ap.add_argument("--label", default="", help="Optional display label")

    ap.add_argument("--source-kind", default="import_path", help="source_kind: upload|import_path|generated")
    ap.add_argument("--source-path", default="", help="Original source path (optional; defaults to --path)")
    ap.add_argument("--collected-at", default="", help="ISO datetime when collected/run occurred")
    ap.add_argument("--instrument", default="", help="Instrument (optional)")
    ap.add_argument("--operator", default="", help="Operator (optional)")
    ap.add_argument("--run-id", default="", help="Run ID (optional)")
    ap.add_argument("--tags-json", default="", help="Optional tags JSON")
    ap.add_argument("--notes", default="", help="Optional notes")

    ap.add_argument("--uploads-dir", default="", help="Override uploads directory (defaults to ./uploads relative to PSI base)")

    args = ap.parse_args()

    ensure_schema()

    file_path = Path(args.path).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        raise SystemExit(f"File not found: {file_path}")

    data = file_path.read_bytes()
    filename = file_path.name

    if args.uploads_dir:
        base_dir = Path(args.uploads_dir).expanduser().resolve().parent
        cfg = StorageConfig(base_dir=base_dir)
    else:
        # Default behavior: StorageConfig expects base_dir such that base_dir/uploads exists.
        # In PSI, base_dir is repo_root/psi by default via get_storage_cfg(). Here we mimic
        # by using CWD.
        cfg = StorageConfig(base_dir=Path.cwd())

    ensure_storage(cfg)

    with SessionLocal() as db:
        f = save_upload(
            db,
            cfg=cfg,
            filename=filename,
            content_type="application/octet-stream",
            data=data,
            source_kind=args.source_kind or "import_path",
            source_path=(args.source_path or str(file_path)),
            collected_at=(args.collected_at or None),
            instrument=(args.instrument or None),
            operator=(args.operator or None),
            run_id=(args.run_id or None),
            tags_json=(args.tags_json or None),
            notes=(args.notes or None),
        )
        link = link_file(
            db,
            file_id=f.id,
            entity_type=args.entity_type,
            entity_id=args.entity_id,
            role=args.role,
            label=(args.label or None),
            reason=f"import and attach to {args.entity_type}",
        )

    print(f"Imported file_id={f.id} stored_name={f.stored_name} sha256={f.sha256[:12]}...")
    print(f"Linked filelink_id={link.id} to {args.entity_type}#{args.entity_id} role={link.role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
