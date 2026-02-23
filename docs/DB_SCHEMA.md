# PSI SQLite DB Schema Reference

This file exists because PSI overlays intentionally exclude `psi/psi.sqlite` and any other `.sqlite` files.
When debugging or extending PSI, it is still critical to know the **current** DB structure.

## How this file is produced

Generate (or refresh) this document from your local DB:

```bash
(.venv) python -m psi.tools.dump_db_schema --db ./psi/psi.sqlite --out ./docs/DB_SCHEMA.md
```

Commit the updated `docs/DB_SCHEMA.md` alongside any schema/migration changes.

## Notes

- This is **not** a migration log; it is a compact “what tables/columns exist right now” reference.
- If a table/column is renamed, this document should change in the same patch.

