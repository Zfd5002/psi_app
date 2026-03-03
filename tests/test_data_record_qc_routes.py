from __future__ import annotations

from psi.web.routers import data_records


def test_data_record_qc_routes_exposed_with_data_and_alias_paths() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set())))) for r in data_records.router.routes}
    assert ("/data/{record_id}/qc/approve", ("POST",)) in route_keys
    assert ("/data/{record_id}/qc/reject", ("POST",)) in route_keys
    assert ("/data-records/{record_id}/qc/approve", ("POST",)) in route_keys
    assert ("/data-records/{record_id}/qc/reject", ("POST",)) in route_keys
