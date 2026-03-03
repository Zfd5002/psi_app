from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


REPORT_REL_PATH = "_artifacts/ui_label_audit/UI_UNDERSCORE_REPORT.md"

SCAN_GLOBS = [
    "psi/web/templates/**/*.html",
    "psi/web/static/**/*",
    "psi/web/ui_labels.py",
    "tests/test_*template*.py",
    "tests/test_*board*.py",
    "tests/test_*report*.py",
]

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("jinja_replace_filter", re.compile(r"\|\s*replace\(\s*['_\"]_['\"]\s*,\s*['\" ][^)]*\)")),
    ("domain_token_with_underscore", re.compile(r"\b[A-Z]{2,}(?:_[A-Z0-9]+)+(?:/[A-Z0-9_]+)+\b")),
    ("literal_token_with_underscore", re.compile(r"\b(?:not_assessed|policy_version|gate_key|metric_key|blocker_key|rule_id|snapshot_id|inputs_summary)\b")),
    ("direct_key_render_no_humanize", re.compile(r"\{\{[^}\n]*(?:key|state|status|metric_key|gate_key|blocker_key)[^}\n]*\}\}")),
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for pattern in SCAN_GLOBS:
        for p in root.glob(pattern):
            if p.is_file():
                out.append(p)
    return sorted(set(out), key=lambda p: str(p))


def _line_finding_exclusions(category: str, line: str) -> bool:
    if category == "direct_key_render_no_humanize" and "humanize_" in line:
        return True
    return False


def run_audit() -> tuple[list[dict[str, str]], Counter[str]]:
    root = _repo_root()
    findings: list[dict[str, str]] = []
    for path in _iter_files(root):
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.rstrip()
            for category, pattern in PATTERNS:
                if pattern.search(line):
                    if _line_finding_exclusions(category, line):
                        continue
                    findings.append(
                        {
                            "category": category,
                            "file": str(rel),
                            "line": str(lineno),
                            "snippet": line.strip(),
                        }
                    )
    findings = sorted(findings, key=lambda f: (f["category"], f["file"], int(f["line"]), f["snippet"]))
    counts = Counter(f["category"] for f in findings)
    return findings, counts


def write_report(findings: list[dict[str, str]], counts: Counter[str]) -> Path:
    root = _repo_root()
    report_path = root / REPORT_REL_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# UI Underscore Label Audit")
    lines.append("")
    lines.append(f"- Repo root: `{root}`")
    lines.append(f"- Total findings: `{len(findings)}`")
    lines.append("")
    lines.append("## Findings by Category")
    lines.append("")
    if counts:
        for category in sorted(counts):
            lines.append(f"- `{category}`: `{counts[category]}`")
    else:
        lines.append("- No findings.")
    lines.append("")
    lines.append("## Detailed Findings")
    lines.append("")
    lines.append("| Category | File | Line | Snippet |")
    lines.append("|---|---|---:|---|")
    if findings:
        for f in findings:
            snippet = f["snippet"].replace("|", "\\|")
            lines.append(f"| {f['category']} | `{f['file']}` | {f['line']} | `{snippet}` |")
    else:
        lines.append("| none | n/a | 0 | n/a |")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    findings, counts = run_audit()
    report_path = write_report(findings, counts)
    summary = ", ".join(f"{k}={counts[k]}" for k in sorted(counts)) if counts else "none"
    print(f"ui_label_audit: report={report_path}")
    print(f"ui_label_audit: total={len(findings)} categories={summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
