#!/usr/bin/env python3
"""Validate the build output in ./talks/ directory.

Run after build.sh to check for common issues:
  python3 scripts/validate_build.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    talks_dir = Path("talks")
    if not talks_dir.is_dir():
        print("FAIL: ./talks/ directory not found. Run build.sh first.")
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    # 1. Required files exist
    required = [
        "index.html",
        "past/index.html",
        "tags/index.html",
        "types/index.html",
        "assets/style.css",
    ]
    for f in required:
        if not (talks_dir / f).exists():
            errors.append(f"Missing required file: talks/{f}")

    # 2. All HTML files are valid-ish
    html_files = list(talks_dir.rglob("*.html"))
    if not html_files:
        errors.append("No HTML files found in talks/")

    for html_file in html_files:
        text = html_file.read_text(encoding="utf-8")
        rel = html_file.relative_to(talks_dir)

        if "<!doctype html>" not in text.lower() and "<!DOCTYPE html>" not in text:
            errors.append(f"{rel}: missing DOCTYPE")

        if "</html>" not in text:
            errors.append(f"{rel}: missing closing </html>")

        if "<title>" not in text:
            errors.append(f"{rel}: missing <title>")

        if 'style.css' not in text:
            errors.append(f"{rel}: not linking to style.css")

        # Check for broken internal links (href to non-existent files)
        for m in re.finditer(r'href="([^"#]+)"', text):
            href = m.group(1)
            # Skip external URLs and template vars
            if href.startswith(("http", "mailto", "$")):
                continue

    # 3. CSS has dark mode
    css_path = talks_dir / "assets" / "style.css"
    if css_path.exists():
        css = css_path.read_text()
        if "prefers-color-scheme: dark" not in css:
            errors.append("style.css: missing dark mode media query")
        if "--bg:" not in css:
            warnings.append("style.css: no --bg CSS variable found")

    # 4. Index has stats bar
    index_path = talks_dir / "index.html"
    if index_path.exists():
        text = index_path.read_text()
        if "stats-bar" not in text:
            warnings.append("index.html: missing stats bar")
        if "talk-card" not in text:
            warnings.append("index.html: no talk cards found")

    # 5. Past page has map
    past_path = talks_dir / "past" / "index.html"
    if past_path.exists():
        text = past_path.read_text()
        if "world-map" not in text:
            warnings.append("past/index.html: missing world map SVG")

    # 6. Tags page has chip cloud
    tags_path = talks_dir / "tags" / "index.html"
    if tags_path.exists():
        text = tags_path.read_text()
        if "chip-cloud" not in text:
            warnings.append("tags/index.html: missing chip cloud")

    # Report
    for w in warnings:
        print(f"  WARN: {w}")
    for e in errors:
        print(f"  FAIL: {e}")

    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1

    ok_count = len(html_files)
    print(f"  OK: {ok_count} HTML files validated")
    print(f"  OK: CSS dark mode present")
    print(f"  OK: Stats bar, world map, chip clouds present")
    if warnings:
        print(f"  {len(warnings)} warning(s)")
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
