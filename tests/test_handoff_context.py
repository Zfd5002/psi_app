from __future__ import annotations

from types import SimpleNamespace

from psi.web import handoff_context as hc


def test_parse_handoff_context_normalizes_fields() -> None:
    ctx = hc.parse_handoff_context(
        {
            "source": "Workflow",
            "task_id": "12",
            "return_to": "/programs/1/workflow",
            "captured": "1",
            "updated": "true",
            "next": "Evidence",
            "from_task": "yes",
        }
    )
    assert ctx.source == "workflow"
    assert ctx.task_id == 12
    assert ctx.return_to == "/programs/1/workflow"
    assert ctx.captured is True
    assert ctx.updated is True
    assert ctx.next_step == "evidence"
    assert ctx.from_task is True


def test_build_return_url_encodes_handoff_query() -> None:
    out = hc.build_return_url(
        "/data/7",
        source="board",
        task_id=55,
        return_to="/programs/1/workflow",
        captured=True,
        next_step="evidence",
        from_task=True,
    )
    assert out.startswith("/data/7?")
    assert "source=board" in out
    assert "task_id=55" in out
    assert "captured=1" in out
    assert "next=evidence" in out
    assert "from_task=1" in out
    assert "return_to=%2Fprograms%2F1%2Fworkflow" in out


def test_build_capture_notice_uses_context_and_defaults() -> None:
    notice = hc.build_capture_notice(
        context=hc.HandoffContext(
            captured=True,
            updated=False,
            from_task=True,
            next_step="evidence",
            return_to="/programs/3/workflow",
        ),
        message="Continue in workflow.",
    )
    assert notice["captured"] is True
    assert notice["updated"] is False
    assert notice["from_task"] is True
    assert notice["next_step"] == "evidence"
    assert notice["return_to"] == "/programs/3/workflow"
    assert notice["message"] == "Continue in workflow."


def test_build_capture_notice_supports_legacy_evidence_query_alias() -> None:
    req = SimpleNamespace(query_params={"evidence": "1"})
    notice = hc.build_capture_notice(request=req, return_to="/programs/2/workflow")
    assert notice["updated"] is True
    assert notice["return_to"] == "/programs/2/workflow"
