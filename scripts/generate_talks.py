#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import calendar
from collections import defaultdict



AUTO_START = "<!-- AUTO-GENERATED START -->"
AUTO_END = "<!-- AUTO-GENERATED END -->"

NOTES_START = "<!-- NOTES START (you can edit freely) -->"
NOTES_END = "<!-- NOTES END -->"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _safe_slug(s: str) -> str:
    s = _norm(s).lower()
    s = re.sub(r"[^a-z0-9\- ]+", "", s)
    s = s.replace(" ", "-")
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "item"


def _parse_iso_date(s: str) -> Optional[date]:
    s = _norm(s)
    if not s:
        return None
    # Accept YYYY-MM-DD
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        pass
    # Accept YYYYMMDD
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_time(s: str) -> Optional[str]:
    s = _norm(s)
    if not s:
        return None
    # allow HH:MM or H:MM
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if not m:
        return s  # leave as-is; better than losing it
    hh = int(m.group(1))
    mm = int(m.group(2))
    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return f"{hh:02d}:{mm:02d}"
    return s


def _split_tags(s: str) -> List[str]:
    s = _norm(s)
    if not s:
        return []
    # user said: lowercase, comma-separated
    parts = [p.strip().lower() for p in s.split(",")]
    return [p for p in parts if p]


def _md_link(label: str, url: str) -> str:
    url = _norm(url)
    if not url:
        return label
    return f"[{label}]({url})"


def _yaml_escape(s: str) -> str:
    # conservative quoted YAML
    s = (s or "").replace('"', '\\"')
    return f'"{s}"'


def _read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, str]] = []
        for r in reader:
            rows.append({k: (v if v is not None else "") for k, v in r.items()})
        return list(reader.fieldnames or []), rows


def _get(row: Dict[str, str], *keys: str) -> str:
    for k in keys:
        if k in row:
            return row.get(k, "") or ""
    return ""


@dataclass
class Talk:
    talk_id: str
    title: str
    meeting: str
    meeting_link: str
    location: str
    start_date: Optional[date]
    end_date: Optional[date]
    talk_date: Optional[date]
    start_time: Optional[str]
    time_zone: str
    duration_min: str
    session: str
    city: str
    country: str
    abstract: str
    slides: str
    recording: str
    status: str
    tags: List[str]
    talk_type: str
    visibility: str

    @property
    def is_public(self) -> bool:
        return _norm(self.visibility).lower() != "private"

    @property
    def status_norm(self) -> str:
        return _norm(self.status)

    @property
    def talk_date_key(self) -> date:
        # for sorting: missing -> far past
        return self.talk_date or date(1900, 1, 1)

    @property
    def time_key(self) -> str:
        return self.start_time or "99:99"

def render_upcoming_calendar_html(upcoming: List[Talk]) -> str:
    """
    Returns raw HTML for one or more month grids covering all upcoming talk dates.
    Expects Talk Date to be present for calendar placement.
    """
    # Keep only talks with dates
    upcoming = [t for t in upcoming if t.talk_date is not None]
    if not upcoming:
        return "<p><em>No upcoming talks listed.</em></p>"

    # Group talks by (year, month, day)
    by_ymd: Dict[Tuple[int, int, int], List[Talk]] = defaultdict(list)
    for t in upcoming:
        d = t.talk_date
        by_ymd[(d.year, d.month, d.day)].append(t)

    # Determine which months to render (all months present in upcoming)
    months = sorted({(t.talk_date.year, t.talk_date.month) for t in upcoming})

    # Calendar where weeks start on Sunday (6 for Sunday in Python? actually setfirstweekday expects 6 for Sunday)
    cal = calendar.Calendar(firstweekday=6)  # Sunday

    dow_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    parts: List[str] = []
    parts.append('<div class="calendar">')

    for (y, m) in months:
        month_name = f"{calendar.month_name[m]} {y}"
        parts.append('<div class="calendar-month">')
        parts.append(f'<div class="calendar-month-header">{month_name}</div>')
        parts.append('<div class="calendar-grid">')

        # day-of-week headers
        for lab in dow_labels:
            parts.append(f'<div class="calendar-dow">{lab}</div>')

        # weeks
        for week in cal.monthdayscalendar(y, m):
            for day in week:
                if day == 0:
                    parts.append('<div class="calendar-cell is-empty"></div>')
                    continue

                items = by_ymd.get((y, m, day), [])
                parts.append('<div class="calendar-cell">')
                parts.append(f'<div class="calendar-daynum">{day}</div>')

                for t in sorted(items, key=lambda x: x.time_key):
                    # Link from /talks/ index to /talks/<id>/ : relative "talks/<id>/" from base
                    href = f"{t.talk_id}/"
                    title = t.title or t.talk_id

                    meta_bits = []
                    if t.start_time:
                        meta_bits.append(t.start_time + (f" {t.time_zone}" if t.time_zone else ""))
                    if t.city or t.country:
                        meta_bits.append(", ".join([p for p in [t.city, t.country] if p]))
                    meta = " • ".join(meta_bits)

                    parts.append(f'<a class="calendar-item" href="{href}">')
                    parts.append(f'<span class="calendar-chip">{title}</span>')
                    if meta:
                        parts.append(f'<span class="calendar-meta">{meta}</span>')
                    parts.append("</a>")

                parts.append("</div>")  # calendar-cell

        parts.append("</div>")  # calendar-grid
        parts.append("</div>")  # calendar-month

    parts.append("</div>")  # calendar
    return "\n".join(parts)

def load_talks(csv_path: Path) -> List[Talk]:
    _, rows = _read_csv(csv_path)
    talks: List[Talk] = []

    for r in rows:
        talk_id = _norm(_get(r, "Talk ID", "TalkID"))
        if not talk_id:
            # fallback: slugify title
            talk_id = _safe_slug(_get(r, "Title"))

        meeting = _norm(_get(r, "Meeting", "Meeting/Venue"))
        meeting_link = _norm(_get(r, "Meeting Link", "MeetingLink"))
        title = _norm(_get(r, "Title"))
        location = _norm(_get(r, "Location"))
        session = _norm(_get(r, "Session"))
        city = _norm(_get(r, "City"))
        country = _norm(_get(r, "Country"))

        start_date = _parse_iso_date(_get(r, "Start Date", "StartDate"))
        end_date = _parse_iso_date(_get(r, "End Date", "EndDate"))
        talk_date = _parse_iso_date(_get(r, "Talk Date", "TalkDate", "Date"))

        start_time = _parse_time(_get(r, "Start Time", "StartTime"))
        time_zone = _norm(_get(r, "Time Zone", "Timezone", "TZ"))

        duration_min = _norm(_get(r, "Duration"))
        abstract = _norm(_get(r, "Abstract", "Abstratct"))
        slides = _norm(_get(r, "Slides"))
        recording = _norm(_get(r, "Recording"))

        status = _norm(_get(r, "Status"))
        tags = _split_tags(_get(r, "Tags"))

        talk_type = _norm(_get(r, "Talk Type", "TalkType", "Type"))
        visibility = _norm(_get(r, "Visibility"))

        talks.append(
            Talk(
                talk_id=talk_id,
                title=title,
                meeting=meeting,
                meeting_link=meeting_link,
                location=location,
                start_date=start_date,
                end_date=end_date,
                talk_date=talk_date,
                start_time=start_time,
                time_zone=time_zone,
                duration_min=duration_min,
                session=session,
                city=city,
                country=country,
                abstract=abstract,
                slides=slides,
                recording=recording,
                status=status,
                tags=tags,
                talk_type=talk_type,
                visibility=visibility,
            )
        )

    # de-dup by talk_id (last one wins)
    dedup: Dict[str, Talk] = {}
    for t in talks:
        dedup[t.talk_id] = t
    return list(dedup.values())


def read_existing_notes(md_path: Path) -> str:
    if not md_path.exists():
        return (
            f"{NOTES_START}\n"
            f"(Add your notes here. This block will be preserved when regenerating.)\n"
            f"{NOTES_END}\n"
        )
    txt = md_path.read_text(encoding="utf-8")
    m = re.search(
        re.escape(NOTES_START) + r"(.*?)" + re.escape(NOTES_END),
        txt,
        flags=re.DOTALL,
    )
    if not m:
        # If user removed markers, don't overwrite anything: add a fresh notes block on top.
        return (
            f"{NOTES_START}\n"
            f"(Add your notes here. This block will be preserved when regenerating.)\n"
            f"{NOTES_END}\n"
        )
    return f"{NOTES_START}{m.group(1)}{NOTES_END}\n"


def write_md_with_preserved_notes(md_path: Path, front_matter: Dict[str, Any], auto_block: str) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    notes_block = read_existing_notes(md_path)

    fm_lines = ["---"]
    for k, v in front_matter.items():
        if isinstance(v, list):
            fm_lines.append(f"{k}:")
            for item in v:
                fm_lines.append(f"  - {_yaml_escape(str(item))}")
        elif v is None or v == "":
            fm_lines.append(f"{k}: {_yaml_escape('')}")
        else:
            fm_lines.append(f"{k}: {_yaml_escape(str(v))}")
    fm_lines.append("---\n")

    content = (
        "\n".join(fm_lines)
        + notes_block
        + "\n"
        + f"{AUTO_START}\n"
        + auto_block.rstrip()
        + "\n"
        + f"{AUTO_END}\n"
    )
    md_path.write_text(content, encoding="utf-8")


def talk_auto_block(t: Talk) -> str:
    lines: List[str] = []

    # Header-ish metadata line
    pieces: List[str] = []
    if t.meeting:
        pieces.append(_md_link(t.meeting, t.meeting_link) if t.meeting_link else t.meeting)
    if t.city or t.country:
        loc = ", ".join([p for p in [t.city, t.country] if p])
        pieces.append(loc)
    if t.talk_date:
        d = t.talk_date.strftime("%B %-d, %Y") if hasattr(t.talk_date, "strftime") else str(t.talk_date)
        pieces.append(d)
    time_piece = ""
    if t.start_time:
        time_piece = t.start_time
        if t.time_zone:
            time_piece += f" {t.time_zone}"
    if time_piece:
        pieces.append(time_piece)
    if t.duration_min:
        pieces.append(f"{t.duration_min} min")
    if t.status_norm:
        pieces.append(f"**{t.status_norm}**")
    if t.talk_type:
        pieces.append(t.talk_type)

    if pieces:
        lines.append("> " + " • ".join(pieces))
        lines.append("")

    if t.session:
        lines.append(f"**Session:** {t.session}")
    if t.location:
        lines.append(f"**Location:** {t.location}")
    if t.start_date or t.end_date:
        sd = t.start_date.isoformat() if t.start_date else ""
        ed = t.end_date.isoformat() if t.end_date else ""
        if sd and ed and sd != ed:
            lines.append(f"**Meeting dates:** {sd} – {ed}")
        elif sd:
            lines.append(f"**Meeting date:** {sd}")
    if t.tags:
        tag_links = " ".join([f"[`{tag}`](../../tags/{tag}/)" for tag in t.tags])
        lines.append(f"**Tags:** {tag_links}")
    lines.append("")

    if t.abstract:
        lines.append("## Abstract")
        lines.append(t.abstract)
        lines.append("")

    links: List[str] = []
    if t.slides:
        links.append(_md_link("Slides", t.slides))
    if t.recording:
        links.append(_md_link("Recording", t.recording))
    if links:
        lines.append("## Links")
        lines.append("- " + "\n- ".join(links))
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def list_item_md(t: Talk) -> str:
    # one-line compact entry used in indices
    when = t.talk_date.isoformat() if t.talk_date else ""
    time = (t.start_time + (f" {t.time_zone}" if t.time_zone else "")) if t.start_time else ""
    where = ", ".join([p for p in [t.city, t.country] if p])

    bits: List[str] = []
    if when:
        bits.append(when)
    if time:
        bits.append(time)
    if where:
        bits.append(where)
    if t.status_norm:
        bits.append(t.status_norm)

    meta = " • ".join(bits)
    title = t.title or t.talk_id
    line = f"- **[{title}](../{t.talk_id}/)**"
    if meta:
        line += f"  \n  {meta}"
    if t.meeting:
        meeting = _md_link(t.meeting, t.meeting_link) if t.meeting_link else t.meeting
        line += f"  \n  {meeting}"
    if t.tags:
        tag_links = " ".join([f"[`{tag}`](../tags/{tag}/)" for tag in t.tags])
        line += f"  \n  {tag_links}"
    return line


def write_indices(out_dir: Path, talks: List[Talk]) -> None:
    public = [t for t in talks if t.is_public]

    # Buckets by status
    upcoming = [t for t in public if t.status_norm in {"Scheduled", "Tentative"}]
    completed = [t for t in public if t.status_norm == "Completed"]
    canceled = [t for t in public if t.status_norm == "Canceled"]

    upcoming.sort(key=lambda t: (t.talk_date_key, t.time_key, t.meeting, t.title))
    completed.sort(key=lambda t: (t.talk_date_key, t.time_key, t.meeting, t.title), reverse=True)
    canceled.sort(key=lambda t: (t.talk_date_key, t.time_key, t.meeting, t.title), reverse=True)

    # /talks/index.md
    blocks: List[str] = []
    blocks.append("# Talks\n")

    if upcoming:
        blocks.append("## Upcoming\n")
        # Calendar-like HTML (pandoc will pass through raw HTML)
        blocks.append(render_upcoming_calendar_html(upcoming))
#        blocks.extend([list_item_md(t) for t in upcoming])
    else:
        blocks.append("_No upcoming talks listed._")

    blocks.append("\n## Recently completed\n")
    recent = completed[:12]
    if recent:
        blocks.extend([list_item_md(t) for t in recent])
        blocks.append("\n[See all past talks](past/)\n")
    else:
        blocks.append("_No completed talks listed._")

    if canceled:
        blocks.append("\n<details>\n<summary>Canceled</summary>\n\n")
        blocks.extend([list_item_md(t) for t in canceled])
        blocks.append("\n</details>\n")

    index_path = out_dir / "index.md"
    write_md_with_preserved_notes(
        index_path,
        front_matter={"title": "Talks", "section": "talks", "generated": "true"},
        auto_block="\n".join(blocks),
    )

    # /talks/past/index.md grouped by year
    past_lines: List[str] = ["# Past talks\n"]
    by_year: Dict[int, List[Talk]] = {}
    for t in completed:
        y = (t.talk_date.year if t.talk_date else 1900)
        by_year.setdefault(y, []).append(t)
    for y in sorted(by_year.keys(), reverse=True):
        if y == 1900:
            continue
        past_lines.append(f"## {y}\n")
        for t in sorted(by_year[y], key=lambda x: (x.talk_date_key, x.time_key), reverse=True):
            past_lines.append(list_item_md(t))
        past_lines.append("")

    past_path = out_dir / "past" / "index.md"
    write_md_with_preserved_notes(
        past_path,
        front_matter={"title": "Past talks", "section": "talks", "generated": "true"},
        auto_block="\n".join(past_lines),
    )

    # Tags
    tag_map: Dict[str, List[Talk]] = {}
    for t in public:
        for tag in t.tags:
            tag_map.setdefault(tag, []).append(t)

    tags_index_lines = ["# Tags\n"]
    for tag in sorted(tag_map.keys()):
        tags_index_lines.append(f"- [`{tag}`]({tag}/) ({len(tag_map[tag])})")
    tags_index_path = out_dir / "tags" / "index.md"
    write_md_with_preserved_notes(
        tags_index_path,
        front_matter={"title": "Talk tags", "section": "talks", "generated": "true"},
        auto_block="\n".join(tags_index_lines) + "\n",
    )

    for tag, items in tag_map.items():
        items.sort(key=lambda t: (t.talk_date_key, t.time_key), reverse=True)
        lines = [f"# Tag: `{tag}`\n"]
        upcoming_tag = [t for t in items if t.status_norm in {"Scheduled", "Tentative"}]
        past_tag = [t for t in items if t.status_norm == "Completed"]

        lines.append("## Upcoming\n")
        lines.extend([list_item_md(t) for t in sorted(upcoming_tag, key=lambda t: (t.talk_date_key, t.time_key))] or ["_None._"])
        lines.append("\n## Past\n")
        lines.extend([list_item_md(t) for t in past_tag] or ["_None._"])
        tag_path = out_dir / "tags" / tag / "index.md"
        write_md_with_preserved_notes(
            tag_path,
            front_matter={"title": f"Tag: {tag}", "section": "talks", "generated": "true"},
            auto_block="\n".join(lines) + "\n",
        )

    # Types
    type_map: Dict[str, List[Talk]] = {}
    for t in public:
        k = _safe_slug(t.talk_type) if t.talk_type else "unspecified"
        type_map.setdefault(k, []).append(t)

    types_index_lines = ["# Talk types\n"]
    for k in sorted(type_map.keys()):
        label = k.replace("-", " ").title()
        types_index_lines.append(f"- [{label}]({k}/) ({len(type_map[k])})")
    types_index_path = out_dir / "types" / "index.md"
    write_md_with_preserved_notes(
        types_index_path,
        front_matter={"title": "Talk types", "section": "talks", "generated": "true"},
        auto_block="\n".join(types_index_lines) + "\n",
    )

    for k, items in type_map.items():
        label = k.replace("-", " ").title()
        items.sort(key=lambda t: (t.talk_date_key, t.time_key), reverse=True)
        lines = [f"# Type: {label}\n"]
        lines.extend([list_item_md(t) for t in items] or ["_None._"])
        type_path = out_dir / "types" / k / "index.md"
        write_md_with_preserved_notes(
            type_path,
            front_matter={"title": f"Type: {label}", "section": "talks", "generated": "true"},
            auto_block="\n".join(lines) + "\n",
        )


def main() -> None:
    repo_root = Path(".").resolve()
    csv_path = repo_root / "content" / "talks.csv"
    out_dir = repo_root / "content" / "talks"

    talks = load_talks(csv_path)

    # Per-talk pages
    for t in talks:
        if not t.is_public:
            continue
        md_path = out_dir / t.talk_id / "index.md"
        fm = {
            "title": t.title or t.talk_id,
            "section": "talks",
            "talk_id": t.talk_id,
            "talk_date": t.talk_date.isoformat() if t.talk_date else "",
            "status": t.status_norm,
            "meeting": t.meeting,
            "city": t.city,
            "country": t.country,
            "tags": t.tags,
            "talk_type": t.talk_type,
            "generated": "true",
        }
        write_md_with_preserved_notes(md_path, fm, talk_auto_block(t))

    # Indices
    write_indices(out_dir, talks)


if __name__ == "__main__":
    main()

