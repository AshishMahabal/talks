#!/usr/bin/env bash
set -euo pipefail

BASEURL="${BASEURL:-}"   # e.g. "" locally, "/repo" on GitHub Pages project sites

# 1) Generate Markdown from CSV
python3 scripts/generate_talks.py

# 2) Build output at top-level: ./talks
rm -rf talks
mkdir -p talks/assets
cp -R assets/* talks/assets/

# 3) Convert Markdown to HTML
# content/talks/<...>/index.md -> talks/<...>/index.html
while IFS= read -r -d '' md; do
  rel="${md#content/talks/}"     # strip leading content/talks/
  out="talks/${rel%.md}.html"    # index.md -> index.html
  outdir="$(dirname "$out")"
  mkdir -p "$outdir"

  pandoc "$md" \
    --from markdown \
    --to html5 \
    --standalone \
    --template assets/template.html \
    --metadata baseurl="$BASEURL" \
    --css assets/style.css \
    --output "$out"
done < <(find content/talks -name '*.md' -print0)

echo "Built talks -> ./talks (BASEURL='${BASEURL}')"

