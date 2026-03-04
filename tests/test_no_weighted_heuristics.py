from __future__ import annotations

import inspect
import re

from psi.services import report_engine
from psi.services import v3_ranking


def test_ranking_and_comparative_paths_have_no_inline_weighted_heuristics() -> None:
    sources = [
        inspect.getsource(v3_ranking.build_ranking_surface),
        inspect.getsource(report_engine.generate_molecule_comparative_report_v0),
        inspect.getsource(report_engine.generate_program_comparative_report_v0),
    ]
    joined = "\n".join(sources)
    banned = [
        r"\bweighted\b",
        r"\bweighting\b",
        r"\b0\.5\b",
        r"\b1\.0\b",
        r"\b2\.0\b",
    ]
    for pattern in banned:
        assert re.search(pattern, joined, flags=re.IGNORECASE) is None, f"banned heuristic pattern found: {pattern}"
