#!/usr/bin/env bash
set -euo pipefail

# For repo "talks" on GitHub Pages project site, BASEURL should be "/talks".
# For a user site repo (<user>.github.io), BASEURL should be "".
BASEURL="${BASEURL:-/talks}"

python3 scripts/generate_talks.py

rm -rf talks
mkdir -p talks/assets
cp -R assets/* talks/assets/

# Convert only the generated talks markdown
# content/talks/<...>/index.md -> talks/<...>/index.html
while IFS= read -r -d '' md; do
  rel="${md#content/talks/}"
  out="talks/${rel%.md}.html"
  mkdir -p "$(dirname "$out")"

  pandoc "$md" \
    --from markdown+raw_html \
    --to html5 \
    --standalone \
    --template assets/template.html \
    --metadata baseurl="$BASEURL" \
    --css assets/style.css \
    --output "$out"
done < <(find content/talks -name '*.md' -print0)

echo "Built talks -> ./talks (BASEURL='${BASEURL}')"

