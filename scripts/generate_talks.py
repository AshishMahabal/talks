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

def render_upcoming_cards_html(upcoming: List[Talk]) -> str:
    # Only dated items for ordering
    items = [t for t in upcoming if t.talk_date is not None]
    if not items:
        return "<p><em>No upcoming talks listed.</em></p>"

    # Group by (year, month)
    by_ym: Dict[Tuple[int, int], List[Talk]] = {}
    for t in items:
        key = (t.talk_date.year, t.talk_date.month)
        by_ym.setdefault(key, []).append(t)

    parts: List[str] = []
    parts.append('<div class="board">')

    for (y, m) in sorted(by_ym.keys()):
        month_name = f"{datetime(y, m, 1).strftime('%B %Y')}"
        parts.append('<div class="board-section">')
        parts.append(f'<div class="board-section-title">{month_name}</div>')
        parts.append('<div class="card-grid">')

        for t in sorted(by_ym[(y, m)], key=lambda x: (x.talk_date_key, x.time_key, x.meeting, x.title)):
            # Link from /talks/ index -> /talks/<id>/
            href = f"{t.talk_id}/"
            title = t.title or t.talk_id

            # Topline: date + time + tz
            date_str = t.talk_date.isoformat() if t.talk_date else ""
            time_str = ""
            if t.start_time:
                time_str = t.start_time + (f" {t.time_zone}" if t.time_zone else "")

            where = ", ".join([p for p in [t.city, t.country] if p])

            meeting_html = _md_link(t.meeting, t.meeting_link) if t.meeting_link else t.meeting

            parts.append('<div class="talk-card">')
            parts.append('<div class="talk-topline">')
            if date_str:
                parts.append(f"<span>{date_str}</span>")
            if time_str:
                parts.append(f"<span>{time_str}</span>")
            if t.duration_min:
                parts.append(f"<span>{t.duration_min} min</span>")
            if t.status_norm:
                parts.append(_status_badge(t.status_norm))
            if t.talk_type:
                parts.append(_type_badge(t.talk_type))
            parts.append("</div>")

            parts.append(f'<div class="talk-title"><a href="{href}">{title}</a></div>')

            if meeting_html:
                # meeting_html is markdown link; but we are emitting HTML here.
                # Render meeting link manually to avoid markdown-in-html issues.
                if t.meeting_link:
                    parts.append(f'<div class="talk-sub"><a href="{t.meeting_link}">{t.meeting}</a></div>')
                else:
                    parts.append(f'<div class="talk-sub">{t.meeting}</div>')

            if where:
                parts.append(f'<div class="talk-sub">{where}</div>')

            if t.session:
                parts.append(f'<div class="talk-sub"><strong>Session:</strong> {t.session}</div>')

            # Collapsible abstract
            if t.abstract:
                abstract_text = t.abstract if len(t.abstract) <= 200 else t.abstract[:200] + "…"
                parts.append(f'<details class="card-abstract"><summary>Abstract</summary><p>{abstract_text}</p></details>')

            # Tags chips
            if t.tags:
                parts.append('<div class="chips">')
                for tag in t.tags:
                    parts.append(f'<a class="chip" href="tags/{tag}/">{tag}</a>')
                parts.append("</div>")

            # Links row
            links = []
            if t.slides:
                links.append(f'<a href="{t.slides}">Slides</a>')
            if t.recording:
                links.append(f'<a href="{t.recording}">Recording</a>')
            if links:
                parts.append('<div class="linkrow">' + " ".join(links) + "</div>")

            parts.append("</div>")  # talk-card

        parts.append("</div>")  # card-grid
        parts.append("</div>")  # board-section

    parts.append("</div>")  # board
    return "\n".join(parts)

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
            f"(2026 talks.)\n"
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


COUNTRY_FLAGS: Dict[str, str] = {
    "usa": "\U0001F1FA\U0001F1F8", "india": "\U0001F1EE\U0001F1F3",
    "qatar": "\U0001F1F6\U0001F1E6", "uk": "\U0001F1EC\U0001F1E7",
    "germany": "\U0001F1E9\U0001F1EA", "france": "\U0001F1EB\U0001F1F7",
    "japan": "\U0001F1EF\U0001F1F5", "china": "\U0001F1E8\U0001F1F3",
    "australia": "\U0001F1E6\U0001F1FA", "canada": "\U0001F1E8\U0001F1E6",
    "brazil": "\U0001F1E7\U0001F1F7", "chile": "\U0001F1E8\U0001F1F1",
    "spain": "\U0001F1EA\U0001F1F8", "italy": "\U0001F1EE\U0001F1F9",
    "netherlands": "\U0001F1F3\U0001F1F1", "south korea": "\U0001F1F0\U0001F1F7",
    "mexico": "\U0001F1F2\U0001F1FD", "south africa": "\U0001F1FF\U0001F1E6",
    "switzerland": "\U0001F1E8\U0001F1ED", "sweden": "\U0001F1F8\U0001F1EA",
}


def _country_flag(country: str) -> str:
    return COUNTRY_FLAGS.get(country.lower().strip(), "")


STATUS_COLORS: Dict[str, str] = {
    "scheduled": "#2e7d32",
    "completed": "#1565c0",
    "cancelled": "#c62828",
    "canceled": "#c62828",
    "tentative": "#e65100",
}

TYPE_COLORS: Dict[str, str] = {
    "oral": "#5c35a3",
    "panel": "#00695c",
    "poster": "#ad5700",
    "remote": "#0277bd",
    "soc": "#4e342e",
    "loc": "#37474f",
}


def _badge_html(text: str, color_map: Dict[str, str]) -> str:
    """Return a badge <span> with an inline color if text matches the map."""
    key = text.lower().strip()
    color = color_map.get(key, "")
    style = f' style="background:{color}"' if color else ""
    return f'<span class="badge"{style}>{text}</span>'


def _status_badge(status: str) -> str:
    return _badge_html(status, STATUS_COLORS)


def _type_badge(talk_type: str) -> str:
    # talk_type may be "Oral, Panel" — color by first word
    key = talk_type.lower().split(",")[0].strip()
    color = TYPE_COLORS.get(key, "#546e7a")
    return f'<span class="badge" style="background:{color}">{talk_type}</span>'


def talk_auto_block(t: Talk) -> str:
    lines: List[str] = []

    # Back link
    lines.append('[&larr; All talks](./)\n')

    # Metadata table as HTML for clean layout
    lines.append('<div class="talk-detail">')

    # Status & type badges
    badge_parts: List[str] = []
    if t.status_norm:
        badge_parts.append(_status_badge(t.status_norm))
    if t.talk_type:
        badge_parts.append(_type_badge(t.talk_type))
    if badge_parts:
        lines.append('<div class="talk-detail-badges">' + " ".join(badge_parts) + '</div>')

    # Meeting
    if t.meeting:
        if t.meeting_link:
            lines.append(f'<div class="talk-detail-row"><strong>Meeting:</strong> <a href="{t.meeting_link}">{t.meeting}</a></div>')
        else:
            lines.append(f'<div class="talk-detail-row"><strong>Meeting:</strong> {t.meeting}</div>')

    # Location with flag
    loc_parts = [p for p in [t.city, t.country] if p]
    if loc_parts:
        flag = _country_flag(t.country) + " " if t.country else ""
        lines.append(f'<div class="talk-detail-row"><strong>Location:</strong> {flag}{", ".join(loc_parts)}</div>')

    if t.location:
        lines.append(f'<div class="talk-detail-row"><strong>Venue:</strong> {t.location}</div>')

    # Date & time
    if t.talk_date:
        d = t.talk_date.strftime("%B %-d, %Y")
        time_str = ""
        if t.start_time:
            time_str = f" at {t.start_time}"
            if t.time_zone:
                time_str += f" {t.time_zone}"
        if t.duration_min:
            time_str += f" ({t.duration_min} min)"
        lines.append(f'<div class="talk-detail-row"><strong>Date:</strong> {d}{time_str}</div>')

    if t.start_date or t.end_date:
        sd = t.start_date.isoformat() if t.start_date else ""
        ed = t.end_date.isoformat() if t.end_date else ""
        if sd and ed and sd != ed:
            lines.append(f'<div class="talk-detail-row"><strong>Meeting dates:</strong> {sd} &ndash; {ed}</div>')
        elif sd:
            lines.append(f'<div class="talk-detail-row"><strong>Meeting date:</strong> {sd}</div>')

    if t.session:
        lines.append(f'<div class="talk-detail-row"><strong>Session:</strong> {t.session}</div>')

    # Tags
    if t.tags:
        tag_chips = " ".join([f'<a class="chip" href="tags/{tag}/">{tag}</a>' for tag in t.tags])
        lines.append(f'<div class="talk-detail-row"><strong>Tags:</strong> {tag_chips}</div>')

    # Slides/Recording as buttons
    link_buttons: List[str] = []
    if t.slides:
        link_buttons.append(f'<a class="btn" href="{t.slides}">Slides</a>')
    if t.recording:
        link_buttons.append(f'<a class="btn" href="{t.recording}">Recording</a>')
    if link_buttons:
        lines.append('<div class="talk-detail-links">' + " ".join(link_buttons) + '</div>')

    lines.append('</div>')  # talk-detail

    # Abstract
    if t.abstract:
        lines.append("\n## Abstract\n")
        lines.append(t.abstract)
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
    line = f"- **[{title}]({t.talk_id}/)**"
    if meta:
        line += f"  \n  {meta}"
    if t.meeting:
        meeting = _md_link(t.meeting, t.meeting_link) if t.meeting_link else t.meeting
        line += f"  \n  {meeting}"
    if t.tags:
        tag_links = " ".join([f"[`{tag}`](tags/{tag}/)" for tag in t.tags])
        line += f"  \n  {tag_links}"
    return line


# Simple city -> (lon, lat) lookup for world map dots
# Uses equirectangular projection: x = (lon+180)/360 * width, y = (90-lat)/180 * height
CITY_COORDS: Dict[str, Tuple[float, float]] = {
    "phoenix": (-112.07, 33.45), "baltimore": (-76.61, 39.29),
    "pune": (73.86, 18.52), "doha": (51.53, 25.29),
    "pasadena": (-118.13, 34.15), "tucson": (-110.97, 32.22),
    "seattle": (-122.33, 47.61), "san francisco": (-122.42, 37.77),
    "new york": (-73.94, 40.67), "washington": (-77.04, 38.91),
    "boston": (-71.06, 42.36), "chicago": (-87.63, 41.88),
    "los angeles": (-118.24, 34.05), "honolulu": (-157.86, 21.31),
    "london": (-0.12, 51.51), "paris": (2.35, 48.86),
    "berlin": (13.40, 52.52), "amsterdam": (4.90, 52.37),
    "tokyo": (139.69, 35.69), "beijing": (116.40, 39.90),
    "sydney": (151.21, -33.87), "melbourne": (144.96, -37.81),
    "cape town": (18.42, -33.93), "mumbai": (72.88, 19.08),
    "bangalore": (77.59, 12.97), "delhi": (77.21, 28.61),
    "santiago": (-70.67, -33.45), "mexico city": (-99.13, 19.43),
    "toronto": (-79.38, 43.65), "vancouver": (-123.12, 49.28),
    "geneva": (6.14, 46.20), "zurich": (8.54, 47.38),
    "stockholm": (18.07, 59.33), "heidelberg": (8.69, 49.40),
    "garching": (11.65, 48.25), "leiden": (4.50, 52.16),
    "groningen": (6.57, 53.22), "la serena": (-71.25, -29.91),
    "sao paulo": (-46.63, -23.55), "rio de janeiro": (-43.17, -22.91),
    "edinburgh": (-3.19, 55.95), "madrid": (-3.70, 40.42),
    "rome": (12.50, 41.90), "seoul": (126.98, 37.57),
}


def _ll(lon: float, lat: float, W: int, H: int) -> Tuple[float, float]:
    """Equirectangular projection: lon/lat -> SVG x/y."""
    return (lon + 180) / 360 * W, (90 - lat) / 180 * H


def _continent_path(coords: List[Tuple[float, float]], W: int, H: int) -> str:
    """Convert a list of (lon, lat) to an SVG path string."""
    pts = [_ll(lon, lat, W, H) for lon, lat in coords]
    d = f"M{pts[0][0]:.0f},{pts[0][1]:.0f}"
    for x, y in pts[1:]:
        d += f"L{x:.0f},{y:.0f}"
    return d + "Z"


def _render_world_map(talks: List[Talk]) -> str:
    """Render an SVG world map with simplified continent outlines and city dots."""
    city_counts: Dict[str, int] = {}
    for t in talks:
        key = t.city.lower().strip()
        if key and key in CITY_COORDS:
            city_counts[key] = city_counts.get(key, 0) + 1
    if not city_counts:
        return ""

    W, H = 900, 450

    # Simplified but recognizable continent outlines (lon, lat pairs)
    north_america = [
        (-168, 72), (-140, 70), (-130, 72), (-120, 60), (-80, 62),
        (-65, 48), (-55, 50), (-60, 43), (-75, 35), (-82, 25),
        (-90, 20), (-105, 20), (-118, 33), (-125, 48), (-140, 60),
        (-165, 62), (-168, 72),
    ]
    central_america = [
        (-105, 20), (-90, 20), (-85, 15), (-80, 10), (-82, 8),
        (-87, 12), (-92, 15), (-100, 17), (-105, 20),
    ]
    south_america = [
        (-80, 10), (-75, 12), (-60, 5), (-50, 0), (-35, -5),
        (-35, -15), (-38, -22), (-48, -28), (-55, -34),
        (-65, -55), (-72, -50), (-75, -42), (-72, -18),
        (-80, -3), (-80, 10),
    ]
    europe = [
        (-10, 36), (0, 38), (3, 43), (-5, 44), (-10, 44),
        (-8, 48), (2, 51), (5, 54), (10, 55), (12, 57),
        (18, 60), (25, 65), (30, 70), (32, 72), (28, 72),
        (18, 68), (15, 62), (22, 58), (28, 56), (30, 50),
        (25, 42), (20, 40), (15, 38), (10, 44), (6, 46),
        (3, 43), (0, 38), (-10, 36),
    ]
    africa = [
        (-18, 15), (-15, 28), (-5, 36), (0, 38), (10, 37),
        (12, 33), (32, 32), (43, 12), (50, 12), (42, 0),
        (40, -5), (35, -12), (32, -26), (28, -34), (18, -35),
        (12, -20), (10, -5), (8, 5), (0, 6), (-8, 5),
        (-15, 10), (-18, 15),
    ]
    asia = [
        (28, 72), (40, 70), (60, 72), (70, 73), (100, 72),
        (130, 72), (170, 65), (180, 65), (170, 60), (145, 48),
        (140, 52), (132, 43), (130, 35), (120, 25), (108, 22),
        (105, 12), (100, 2), (96, 6), (80, 8), (77, 15),
        (70, 22), (60, 25), (50, 30), (35, 33), (32, 32),
        (28, 40), (30, 50), (28, 56), (22, 58), (15, 62),
        (18, 68), (28, 72),
    ]
    australia = [
        (114, -12), (130, -12), (137, -15), (145, -15),
        (150, -24), (153, -28), (150, -38), (140, -38),
        (132, -34), (120, -35), (114, -32), (114, -22),
        (114, -12),
    ]

    continents = [north_america, central_america, south_america, europe, africa, asia, australia]

    lines: List[str] = []
    lines.append(f'<div class="world-map"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">')
    lines.append(f'<rect width="{W}" height="{H}" fill="var(--map-bg, #eef2f7)" rx="10"/>')

    # Graticule (light grid lines)
    lines.append('<g stroke="var(--map-grid, #dde3ea)" stroke-width="0.5" fill="none" opacity="0.6">')
    for lat in range(-60, 90, 30):
        _, y = _ll(0, lat, W, H)
        lines.append(f'<line x1="0" y1="{y:.0f}" x2="{W}" y2="{y:.0f}"/>')
    for lon in range(-150, 180, 30):
        x, _ = _ll(lon, 0, W, H)
        lines.append(f'<line x1="{x:.0f}" y1="0" x2="{x:.0f}" y2="{H}"/>')
    lines.append('</g>')

    # Continents
    lines.append('<g fill="var(--map-land, #c8d5e0)" stroke="var(--map-border, #a0b0c0)" stroke-width="0.8">')
    for cont in continents:
        lines.append(f'<path d="{_continent_path(cont, W, H)}"/>')
    lines.append('</g>')

    # City dots with CSS-based tooltip
    for city, count in city_counts.items():
        lon, lat = CITY_COORDS[city]
        x, y = _ll(lon, lat, W, H)
        r = min(4 + count * 2, 12)
        label = f"{city.title()} ({count})"
        # Pulsing dot + label group
        lines.append(f'<g class="map-dot">')
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 4:.1f}" fill="var(--dot-glow, #4a90d9)" opacity="0.2"/>')
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="var(--dot-fill, #3b7dd8)" stroke="#fff" stroke-width="1.5"/>')
        # Label — positioned above the dot
        lines.append(f'<text class="map-label" x="{x:.1f}" y="{y - r - 6:.1f}" text-anchor="middle" fill="var(--text)" font-size="11" font-weight="600">{label}</text>')
        lines.append(f'</g>')

    lines.append('</svg></div>')
    return "\n".join(lines)


def write_indices(out_dir: Path, talks: List[Talk]) -> None:
    public = [t for t in talks if t.is_public]

    # Buckets by status
    upcoming = [t for t in public if t.status_norm in {"Scheduled", "Tentative"}]
    completed = [t for t in public if t.status_norm == "Completed"]
    canceled = [t for t in public if t.status_norm == "Canceled"]

    upcoming.sort(key=lambda t: (t.talk_date_key, t.time_key, t.meeting, t.title))
    completed.sort(key=lambda t: (t.talk_date_key, t.time_key, t.meeting, t.title), reverse=True)
    canceled.sort(key=lambda t: (t.talk_date_key, t.time_key, t.meeting, t.title), reverse=True)

    # Stats
    all_countries = {t.country.strip() for t in public if t.country.strip()}
    all_tags = {tag for t in public for tag in t.tags}
    total = len(public)
    stats_html = (
        f'<div class="stats-bar">'
        f'<span><strong>{total}</strong> talks</span>'
        f'<span><strong>{len(all_countries)}</strong> countries</span>'
        f'<span><strong>{len(all_tags)}</strong> tags</span>'
        f'</div>'
    )

    # /talks/index.md
    blocks: List[str] = []
    blocks.append("# Talks\n")
    blocks.append(stats_html)
    blocks.append("")

    if upcoming:
        blocks.append("## Upcoming\n")
        # Calendar-like HTML (pandoc will pass through raw HTML)
        blocks.append(render_upcoming_cards_html(upcoming))
#        blocks.append(render_upcoming_calendar_html(upcoming))
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
    # World map SVG
    map_svg = _render_world_map(completed)
    if map_svg:
        past_lines.append(map_svg)
        past_lines.append("")
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
    max_tag_count = max((len(v) for v in tag_map.values()), default=1)
    tag_chips: List[str] = []
    for tag in sorted(tag_map.keys()):
        count = len(tag_map[tag])
        size = 0.85 + 0.65 * (count / max_tag_count)
        tag_chips.append(f'<a class="chip cloud-chip" href="{tag}/" style="font-size:{size:.2f}rem">{tag} <small>({count})</small></a>')
    tags_index_lines.append('<div class="chip-cloud">' + "\n".join(tag_chips) + '</div>')
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
    max_type_count = max((len(v) for v in type_map.values()), default=1)
    type_chips: List[str] = []
    for k in sorted(type_map.keys()):
        label = k.replace("-", " ").title()
        count = len(type_map[k])
        size = 0.85 + 0.65 * (count / max_type_count)
        type_chips.append(f'<a class="chip cloud-chip" href="{k}/" style="font-size:{size:.2f}rem">{label} <small>({count})</small></a>')
    types_index_lines.append('<div class="chip-cloud">' + "\n".join(type_chips) + '</div>')
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

