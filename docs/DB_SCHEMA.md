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

## Schema Snapshot (Generated)

<!-- BEGIN AUTO-GENERATED DB SCHEMA -->
_Source DB: `/home/zach/psi_codex/psi/psi.sqlite`_

### Tables

#### audit_events

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | entity_type | TEXT | Y |  |  |
| 2 | entity_id | INTEGER | Y |  |  |
| 3 | action | TEXT | Y |  |  |
| 4 | timestamp | DATETIME | Y |  |  |
| 5 | actor | TEXT | Y |  |  |
| 6 | before_json | TEXT |  |  |  |
| 7 | after_json | TEXT |  |  |  |
| 8 | diff_json | TEXT |  |  |  |
| 9 | reason | TEXT |  |  |  |

#### batches

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | molecule_id | INTEGER | Y |  |  |
| 2 | batch_id | TEXT | Y |  |  |
| 3 | title | TEXT |  |  |  |
| 4 | expression_notes | TEXT |  |  |  |
| 5 | purification_notes | TEXT |  |  |  |
| 6 | created_at | DATETIME | Y |  |  |
| 7 | updated_at | DATETIME | Y |  |  |

#### data_measurements

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER |  |  | Y |
| 1 | data_record_id | INTEGER | Y |  |  |
| 2 | name | TEXT | Y |  |  |
| 3 | value_num | REAL |  |  |  |
| 4 | value_text | TEXT |  |  |  |
| 5 | unit | TEXT |  |  |  |
| 6 | comparator | TEXT |  |  |  |
| 7 | is_primary | INTEGER |  |  |  |
| 8 | is_outlier | INTEGER |  |  |  |
| 9 | created_at | TEXT |  |  |  |
| 10 | updated_at | TEXT |  |  |  |
| 11 | qc_flag | TEXT |  |  |  |
| 12 | qc_note | TEXT |  |  |  |
| 13 | data_type | TEXT |  |  |  |
| 14 | method | TEXT |  |  |  |
| 15 | producer | TEXT |  |  |  |
| 16 | producer_version | TEXT |  |  |  |
| 17 | source_path | TEXT |  |  |  |
| 18 | run_id | TEXT |  |  |  |
| 19 | produced_at | TEXT |  |  |  |
| 20 | notes | TEXT |  |  |  |
| 21 | ignore_for_model | INTEGER | Y | 0 |  |

#### data_records

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | program_id | INTEGER | Y |  |  |
| 2 | molecule_id | INTEGER |  |  |  |
| 3 | batch_id | INTEGER |  |  |  |
| 4 | domain | TEXT | Y |  |  |
| 5 | data_type | TEXT | Y |  |  |
| 6 | method | TEXT | Y |  |  |
| 7 | title | TEXT | Y |  |  |
| 8 | notes | TEXT |  |  |  |
| 9 | params_json | TEXT |  |  |  |
| 10 | results_json | TEXT |  |  |  |
| 11 | primary_result_text | TEXT |  |  |  |
| 12 | raw_inputs_json | TEXT |  |  |  |
| 13 | derived_outputs_json | TEXT |  |  |  |
| 14 | is_included | INTEGER | Y |  |  |
| 15 | excluded_reason | TEXT |  |  |  |
| 16 | run_date | TEXT |  |  |  |
| 17 | created_at | DATETIME | Y |  |  |
| 18 | updated_at | DATETIME | Y |  |  |

#### decision_snapshots

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | program_id | INTEGER | Y |  |  |
| 2 | molecule_id | INTEGER |  |  |  |
| 3 | batch_id | INTEGER |  |  |  |
| 4 | decision_key | TEXT | Y |  |  |
| 5 | rules_version | TEXT | Y |  |  |
| 6 | engine_key | TEXT |  |  |  |
| 7 | schema_version | TEXT |  |  |  |
| 8 | inputs_json | TEXT | Y |  |  |
| 9 | outputs_json | TEXT | Y |  |  |
| 10 | evidence_ids_json | TEXT | Y |  |  |
| 11 | as_of_ts | DATETIME |  |  |  |
| 12 | notes | TEXT |  |  |  |
| 13 | is_superseded | INTEGER |  |  |  |
| 14 | superseded_by_snapshot_id | INTEGER |  |  |  |
| 15 | superseded_at | DATETIME |  |  |  |
| 16 | created_at | DATETIME | Y |  |  |

#### domain_artifacts

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | sequence_id | INTEGER | Y |  |  |
| 2 | artifact_type | TEXT | Y |  |  |
| 3 | domain_type | TEXT |  |  |  |
| 4 | tool_name | TEXT | Y |  |  |
| 5 | tool_version | TEXT | Y |  |  |
| 6 | settings_hash | TEXT | Y |  |  |
| 7 | status | TEXT | Y |  |  |
| 8 | result_json | TEXT |  |  |  |
| 9 | error | TEXT |  |  |  |
| 10 | created_at | DATETIME | Y |  |  |
| 11 | updated_at | DATETIME | Y |  |  |

#### domain_instances

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | molecule_id | INTEGER | Y |  |  |
| 2 | component_id | INTEGER | Y |  |  |
| 3 | domain_type | TEXT | Y |  |  |
| 4 | start_idx | INTEGER | Y |  |  |
| 5 | end_idx | INTEGER | Y |  |  |
| 6 | domain_sequence_id | INTEGER |  |  |  |
| 7 | source | TEXT | Y |  |  |
| 8 | method | TEXT |  |  |  |
| 9 | tool_name | TEXT |  |  |  |
| 10 | tool_version | TEXT |  |  |  |
| 11 | settings_hash | TEXT |  |  |  |
| 12 | status | TEXT | Y |  |  |
| 13 | warnings_json | TEXT |  |  |  |
| 14 | error | TEXT |  |  |  |
| 15 | created_at | DATETIME | Y |  |  |
| 16 | updated_at | DATETIME | Y |  |  |

#### evidence

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | program_id | INTEGER | Y |  |  |
| 2 | molecule_id | INTEGER |  |  |  |
| 3 | batch_id | INTEGER |  |  |  |
| 4 | domain | TEXT | Y |  |  |
| 5 | evidence_type | TEXT | Y |  |  |
| 6 | strength | INTEGER | Y |  |  |
| 7 | summary | TEXT | Y |  |  |
| 8 | details | TEXT |  |  |  |
| 9 | created_at | DATETIME | Y |  |  |
| 10 | updated_at | DATETIME | Y |  |  |

#### evidence_citations

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | evidence_id | INTEGER | Y |  |  |
| 2 | data_record_id | INTEGER | Y |  |  |
| 3 | created_at | DATETIME | Y |  |  |

#### file_derivations

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | parent_file_id | INTEGER | Y |  |  |
| 2 | child_file_id | INTEGER | Y |  |  |
| 3 | transform | TEXT |  |  |  |
| 4 | tool_name | TEXT |  |  |  |
| 5 | tool_version | TEXT |  |  |  |
| 6 | created_at | DATETIME | Y |  |  |

#### file_links

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | file_id | INTEGER | Y |  |  |
| 2 | entity_type | TEXT | Y |  |  |
| 3 | entity_id | INTEGER | Y |  |  |
| 4 | role | TEXT |  |  |  |
| 5 | label | TEXT |  |  |  |
| 6 | created_at | DATETIME | Y |  |  |

#### files

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | stored_name | TEXT | Y |  |  |
| 2 | original_name | TEXT | Y |  |  |
| 3 | size_bytes | INTEGER | Y |  |  |
| 4 | mime | TEXT |  |  |  |
| 5 | sha256 | TEXT | Y |  |  |
| 6 | source_kind | TEXT |  |  |  |
| 7 | source_path | TEXT |  |  |  |
| 8 | collected_at | DATETIME |  |  |  |
| 9 | imported_at | DATETIME |  |  |  |
| 10 | instrument | TEXT |  |  |  |
| 11 | operator | TEXT |  |  |  |
| 12 | run_id | TEXT |  |  |  |
| 13 | tags_json | TEXT |  |  |  |
| 14 | notes | TEXT |  |  |  |
| 15 | created_at | DATETIME | Y |  |  |

#### measurement_qc

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | measurement_id | INTEGER | Y |  |  |
| 2 | record_id | INTEGER |  |  |  |
| 3 | metric_key | TEXT |  |  |  |
| 4 | status | TEXT | Y |  |  |
| 5 | ignore_policy | TEXT | Y |  |  |
| 6 | ignore_reason_code | TEXT |  |  |  |
| 7 | ignore_note | TEXT |  |  |  |
| 8 | last_event_id | INTEGER |  |  |  |
| 9 | updated_at | DATETIME | Y |  |  |

#### measurement_qc_events

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | measurement_id | INTEGER | Y |  |  |
| 2 | record_id | INTEGER |  |  |  |
| 3 | metric_key | TEXT |  |  |  |
| 4 | action | TEXT | Y |  |  |
| 5 | status_after | TEXT | Y |  |  |
| 6 | actor | TEXT | Y |  |  |
| 7 | note | TEXT |  |  |  |
| 8 | ignore_policy | TEXT |  |  |  |
| 9 | ignore_reason_code | TEXT |  |  |  |
| 10 | ignore_note | TEXT |  |  |  |
| 11 | created_at | DATETIME | Y |  |  |

#### molecule_components

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | molecule_id | INTEGER | Y |  |  |
| 2 | role | TEXT | Y |  |  |
| 3 | fasta | TEXT | Y |  |  |
| 4 | sha256 | TEXT | Y |  |  |
| 5 | sequence_entity_id | INTEGER |  |  |  |
| 6 | created_at | DATETIME | Y |  |  |
| 7 | updated_at | DATETIME | Y |  |  |

#### molecules

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | program_id | INTEGER | Y |  |  |
| 2 | primary_id | TEXT | Y |  |  |
| 3 | composition_sha256 | TEXT |  |  |  |
| 4 | title | TEXT |  |  |  |
| 5 | description | TEXT |  |  |  |
| 6 | molecule_format | TEXT |  |  |  |
| 7 | description_auto | TEXT |  |  |  |
| 8 | description_user | TEXT |  |  |  |
| 9 | heavy_compute_enabled | INTEGER | Y |  |  |
| 10 | sequences | TEXT |  |  |  |
| 11 | created_at | DATETIME | Y |  |  |
| 12 | updated_at | DATETIME | Y |  |  |

#### outcome_labels

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | snapshot_id | INTEGER | Y |  |  |
| 2 | name | TEXT | Y |  |  |
| 3 | value_text | TEXT |  |  |  |
| 4 | value_num | FLOAT |  |  |  |
| 5 | value_bool | INTEGER |  |  |  |
| 6 | version | TEXT | Y |  |  |
| 7 | created_at | DATETIME | Y |  |  |

#### programs

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | name | TEXT | Y |  |  |
| 2 | description | TEXT |  |  |  |
| 3 | created_at | DATETIME | Y |  |  |
| 4 | updated_at | DATETIME | Y |  |  |

#### property_run_events

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | run_id | INTEGER | Y |  |  |
| 2 | molecule_id | INTEGER | Y |  |  |
| 3 | timestamp | DATETIME | Y |  |  |
| 4 | step | TEXT | Y |  |  |
| 5 | level | TEXT | Y |  |  |
| 6 | message | TEXT | Y |  |  |
| 7 | payload_json | TEXT |  |  |  |

#### property_runs

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | molecule_id | INTEGER | Y |  |  |
| 2 | input_hash | TEXT | Y |  |  |
| 3 | trigger_reason | TEXT | Y |  |  |
| 4 | compute_tier | TEXT | Y |  |  |
| 5 | status | TEXT | Y |  |  |
| 6 | error | TEXT |  |  |  |
| 7 | created_at | DATETIME | Y |  |  |
| 8 | updated_at | DATETIME | Y |  |  |

#### property_values

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | run_id | INTEGER | Y |  |  |
| 2 | molecule_id | INTEGER | Y |  |  |
| 3 | property_key | TEXT | Y |  |  |
| 4 | label | TEXT | Y |  |  |
| 5 | value_json | TEXT |  |  |  |
| 6 | tier | TEXT | Y |  |  |
| 7 | created_at | DATETIME | Y |  |  |

#### sequence_entities

| cid | name | type | notnull | default | pk |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | id | INTEGER | Y |  | Y |
| 1 | chain_id | TEXT |  |  |  |
| 2 | sha256 | TEXT | Y |  |  |
| 3 | sequence_norm | TEXT | Y |  |  |
| 4 | type_hint | TEXT |  |  |  |
| 5 | notes | TEXT |  |  |  |
| 6 | length | INTEGER | Y |  |  |
| 7 | alphabet | TEXT | Y |  |  |
| 8 | created_at | DATETIME | Y |  |  |

<!-- END AUTO-GENERATED DB SCHEMA -->
