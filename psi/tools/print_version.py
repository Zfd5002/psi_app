"""Print the canonical PSI version.

Official stable verification entrypoint:

  python -m psi.tools.print_version

By default prints only the version string (e.g. "v1.2.9h1").
Use --verbose for extra context.
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from psi.version import PSI_VERSION


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--verbose", action="store_true", help="Print extra context.")
    args = p.parse_args(argv)

    # Default: print only the version, nothing else.
    if not args.verbose:
        print(PSI_VERSION)
        return

    repo_root = Path(__file__).resolve().parents[2]
    print(f"PSI_VERSION: {PSI_VERSION}")
    print(f"repo_root: {repo_root}")
    print(f"python: {sys.version.split()[0]}")
    print(f"platform: {platform.platform()}")


if __name__ == "__main__":
    main()
