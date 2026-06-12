#!/usr/bin/env python3
"""Run the weekly Health-AI pipeline and optionally publish it with Git."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from pdf_report import write_pdf


def run(command, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=str(cwd), text=True, check=check)


def publish(base_dir: Path, report_paths) -> None:
    run(["git", "add", "README.md", "agent.py", "config.json", "pdf_report.py", "weekly.py", "test_agent.py", ".gitignore", *[str(path.relative_to(base_dir)) for path in report_paths]], base_dir)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(base_dir)).returncode != 0
    if not changed:
        print("Keine Git-Änderungen zum Veröffentlichen.")
        return
    report_date = datetime.now().date().isoformat()
    run(["git", "commit", "-m", f"Add Health-AI weekly report {report_date}"], base_dir)
    run(["git", "push", "origin", "HEAD"], base_dir)


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-publish", action="store_true", help="Create reports without Git commit/push")
    args = parser.parse_args()

    run([sys.executable, "agent.py", "--days", "7", "--max-items", "20"], base_dir)
    stem = datetime.now().date().isoformat()
    markdown_path = base_dir / "output" / f"{stem}.md"
    pdf_path = base_dir / "output" / f"{stem}.pdf"
    write_pdf(markdown_path, pdf_path)
    print(pdf_path)

    if not args.no_publish:
        publish(base_dir, [markdown_path, pdf_path])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
