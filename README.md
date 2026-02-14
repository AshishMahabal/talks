# Talks & Engagements

A static site to track forthcoming and past conference talks, panels, posters, and organizing activities.

**Live site:** https://ashishmahabal.github.io/talks/index.html

## Features

- **Card view** for upcoming talks grouped by month, with collapsible abstracts
- **Past talks** page with an SVG world map showing talk locations
- **Tag & type pages** with sized chip clouds
- **Individual talk pages** with structured metadata, country flags, and slide/recording buttons
- **Stats bar** showing total talks, countries, and tags
- **Dark mode** via `prefers-color-scheme` (automatic, follows OS)
- **Mobile responsive** layout

## How it works

```
Google Sheet → talks.csv → generate_talks.py → Markdown → Pandoc → HTML
```

1. Talks are maintained in a Google Sheet, downloaded as `content/talks.csv`
2. `scripts/generate_talks.py` reads the CSV and generates Markdown files with YAML front matter
3. `build.sh` runs the generator then converts Markdown to HTML using Pandoc with a custom template

## Build

```bash
# Prerequisites: python3, pandoc
./build.sh

# Output goes to ./talks/
open talks/index.html
```

For GitHub Pages (project site):
```bash
BASEURL="/talks" ./build.sh
```

## Test & validate

```bash
# Unit + integration tests (69 tests)
python3 -m pytest tests/ -v

# Build output validation
python3 scripts/validate_build.py
```

## Project structure

```
content/talks.csv          # Source data (from Google Sheets)
scripts/generate_talks.py  # CSV → Markdown generator
scripts/validate_build.py  # Post-build validation
assets/template.html       # Pandoc HTML template
assets/style.css           # Styles (light + dark mode)
tests/                     # pytest test suite
build.sh                   # Build script
talks/                     # Generated output (git-ignored or committed for GH Pages)
```

## CSV columns

Talk ID, Meeting, Meeting Link, Location, Start Date, End Date, Title, Talk Date, Start Time, Timezone, Duration, Session, City, Country, Abstract, Slides, Recording, Status, Tags, Talk Type, Visibility

- **Talk types:** oral, panel, remote, poster, SOC, LOC (can be multiple, comma-separated)
- **Visibility:** public or private
- **Status:** completed, scheduled, cancelled, or tentative
- **Tags:** comma-separated, lowercased automatically
