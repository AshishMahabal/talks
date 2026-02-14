#!/usr/bin/env python3
"""Tests for scripts/generate_talks.py"""
from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest

# Make scripts importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from generate_talks import (
    CITY_COORDS,
    COUNTRY_FLAGS,
    Talk,
    _continent_path,
    _country_flag,
    _ll,
    _norm,
    _parse_iso_date,
    _parse_time,
    _render_world_map,
    _safe_slug,
    _split_tags,
    _status_badge,
    _type_badge,
    _yaml_escape,
    list_item_md,
    load_talks,
    read_existing_notes,
    render_upcoming_cards_html,
    talk_auto_block,
    write_indices,
    write_md_with_preserved_notes,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _make_talk(**overrides) -> Talk:
    defaults = dict(
        talk_id="test-talk",
        title="Test Talk",
        meeting="Test Conf",
        meeting_link="https://example.com",
        location="Room 101",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 3),
        talk_date=date(2026, 3, 2),
        start_time="10:00",
        time_zone="PT",
        duration_min="30",
        session="Session A",
        city="Phoenix",
        country="USA",
        abstract="An abstract about things.",
        slides="https://slides.example.com",
        recording="https://rec.example.com",
        status="Scheduled",
        tags=["ml", "astro"],
        talk_type="Oral",
        visibility="Public",
    )
    defaults.update(overrides)
    return Talk(**defaults)


# ── Unit tests: parsing helpers ──────────────────────────────────────────


class TestNorm:
    def test_strips_whitespace(self):
        assert _norm("  hello   world  ") == "hello world"

    def test_empty(self):
        assert _norm("") == ""
        assert _norm(None) == ""


class TestSafeSlug:
    def test_basic(self):
        assert _safe_slug("Hello World!") == "hello-world"

    def test_special_chars(self):
        assert _safe_slug("A & B / C") == "a-b-c"

    def test_empty_fallback(self):
        assert _safe_slug("") == "item"
        assert _safe_slug("!!!") == "item"


class TestParseIsoDate:
    def test_iso_format(self):
        assert _parse_iso_date("2026-03-10") == date(2026, 3, 10)

    def test_compact_format(self):
        assert _parse_iso_date("20260310") == date(2026, 3, 10)

    def test_empty(self):
        assert _parse_iso_date("") is None
        assert _parse_iso_date("   ") is None

    def test_invalid(self):
        assert _parse_iso_date("not-a-date") is None


class TestParseTime:
    def test_hhmm(self):
        assert _parse_time("9:30") == "09:30"
        assert _parse_time("14:05") == "14:05"

    def test_empty(self):
        assert _parse_time("") is None

    def test_passthrough(self):
        # Non-matching formats pass through
        assert _parse_time("1025") == "1025"


class TestSplitTags:
    def test_basic(self):
        assert _split_tags("Astro, ML, LLM") == ["astro", "ml", "llm"]

    def test_empty(self):
        assert _split_tags("") == []

    def test_single(self):
        assert _split_tags("astro") == ["astro"]


class TestYamlEscape:
    def test_basic(self):
        assert _yaml_escape("hello") == '"hello"'

    def test_quotes(self):
        assert _yaml_escape('say "hi"') == '"say \\"hi\\""'

    def test_none(self):
        assert _yaml_escape(None) == '""'


# ── Unit tests: Talk model ──────────────────────────────────────────────


class TestTalkModel:
    def test_is_public(self):
        assert _make_talk(visibility="Public").is_public is True
        assert _make_talk(visibility="private").is_public is False
        assert _make_talk(visibility="Private").is_public is False
        assert _make_talk(visibility="").is_public is True

    def test_status_norm(self):
        assert _make_talk(status="Scheduled").status_norm == "Scheduled"
        assert _make_talk(status="  completed ").status_norm == "completed"

    def test_talk_date_key_missing(self):
        t = _make_talk(talk_date=None)
        assert t.talk_date_key == date(1900, 1, 1)

    def test_time_key_missing(self):
        t = _make_talk(start_time=None)
        assert t.time_key == "99:99"


# ── Unit tests: badge helpers ────────────────────────────────────────────


class TestBadges:
    def test_status_badge_scheduled(self):
        html = _status_badge("Scheduled")
        assert 'class="badge"' in html
        assert "#2e7d32" in html
        assert "Scheduled" in html

    def test_status_badge_unknown(self):
        html = _status_badge("Unknown")
        assert 'style=' not in html

    def test_type_badge(self):
        html = _type_badge("Oral")
        assert "#5c35a3" in html

    def test_type_badge_composite(self):
        html = _type_badge("Oral, Panel")
        # Should use color for first type (oral)
        assert "#5c35a3" in html
        assert "Oral, Panel" in html


class TestCountryFlag:
    def test_known(self):
        assert _country_flag("USA") != ""
        assert _country_flag("India") != ""

    def test_unknown(self):
        assert _country_flag("Atlantis") == ""

    def test_case_insensitive(self):
        assert _country_flag("usa") == _country_flag("USA")


# ── Unit tests: map helpers ──────────────────────────────────────────────


class TestMapHelpers:
    def test_ll_projection(self):
        # Center of map
        x, y = _ll(0, 0, 900, 450)
        assert x == 450.0
        assert y == 225.0

    def test_ll_top_left(self):
        x, y = _ll(-180, 90, 900, 450)
        assert x == 0.0
        assert y == 0.0

    def test_continent_path(self):
        path = _continent_path([(0, 0), (10, 0), (10, 10), (0, 10)], 900, 450)
        assert path.startswith("M")
        assert path.endswith("Z")
        assert "L" in path


class TestRenderWorldMap:
    def test_empty_talks(self):
        assert _render_world_map([]) == ""

    def test_unknown_city_skipped(self):
        t = _make_talk(city="Atlantis")
        assert _render_world_map([t]) == ""

    def test_known_city_renders(self):
        t = _make_talk(city="Phoenix")
        svg = _render_world_map([t])
        assert "world-map" in svg
        assert "map-dot" in svg
        assert "Phoenix" in svg

    def test_multiple_same_city(self):
        talks = [_make_talk(city="Pune"), _make_talk(city="Pune", talk_id="t2")]
        svg = _render_world_map(talks)
        assert "Pune (2)" in svg


# ── Unit tests: output rendering ─────────────────────────────────────────


class TestTalkAutoBlock:
    def test_contains_back_link(self):
        block = talk_auto_block(_make_talk())
        assert "All talks" in block

    def test_contains_meeting_link(self):
        block = talk_auto_block(_make_talk())
        assert "https://example.com" in block

    def test_contains_flag(self):
        block = talk_auto_block(_make_talk(country="USA"))
        assert COUNTRY_FLAGS["usa"] in block

    def test_contains_abstract(self):
        block = talk_auto_block(_make_talk(abstract="Important findings."))
        assert "Important findings." in block
        assert "## Abstract" in block

    def test_no_abstract_when_empty(self):
        block = talk_auto_block(_make_talk(abstract=""))
        assert "## Abstract" not in block

    def test_contains_badges(self):
        block = talk_auto_block(_make_talk())
        assert 'class="badge"' in block
        assert "Scheduled" in block
        assert "Oral" in block

    def test_contains_slides_btn(self):
        block = talk_auto_block(_make_talk())
        assert 'class="btn"' in block
        assert "Slides" in block

    def test_contains_tags(self):
        block = talk_auto_block(_make_talk(tags=["ml", "astro"]))
        assert "ml" in block
        assert "astro" in block


class TestRenderUpcomingCards:
    def test_empty(self):
        html = render_upcoming_cards_html([])
        assert "No upcoming" in html

    def test_no_date_filtered(self):
        t = _make_talk(talk_date=None)
        html = render_upcoming_cards_html([t])
        assert "No upcoming" in html

    def test_card_rendered(self):
        t = _make_talk()
        html = render_upcoming_cards_html([t])
        assert "talk-card" in html
        assert "Test Talk" in html
        assert "March 2026" in html

    def test_abstract_details(self):
        t = _make_talk(abstract="Short abstract.")
        html = render_upcoming_cards_html([t])
        assert "card-abstract" in html
        assert "Short abstract." in html

    def test_long_abstract_truncated(self):
        t = _make_talk(abstract="A" * 300)
        html = render_upcoming_cards_html([t])
        assert len("A" * 300) > 200
        # Should end with ellipsis character
        assert "\u2026" in html


class TestListItemMd:
    def test_basic(self):
        md = list_item_md(_make_talk())
        assert "Test Talk" in md
        assert "test-talk" in md
        assert "2026-03-02" in md

    def test_meeting_link(self):
        md = list_item_md(_make_talk())
        assert "Test Conf" in md

    def test_tags(self):
        md = list_item_md(_make_talk(tags=["ai"]))
        assert "`ai`" in md


# ── Integration: CSV loading ─────────────────────────────────────────────


class TestLoadTalks:
    def test_load_real_csv(self):
        csv_path = Path(__file__).resolve().parent.parent / "content" / "talks.csv"
        if not csv_path.exists():
            pytest.skip("talks.csv not found")
        talks = load_talks(csv_path)
        assert len(talks) > 0
        for t in talks:
            assert t.talk_id  # Every talk must have an ID

    def test_dedup(self):
        """Last row wins when IDs collide."""
        csv_path = Path(__file__).resolve().parent.parent / "content" / "talks.csv"
        if not csv_path.exists():
            pytest.skip("talks.csv not found")
        talks = load_talks(csv_path)
        ids = [t.talk_id for t in talks]
        assert len(ids) == len(set(ids))


# ── Integration: write and preserve notes ────────────────────────────────


class TestWriteAndPreserveNotes:
    def test_roundtrip(self, tmp_path):
        md = tmp_path / "talk" / "index.md"
        fm = {"title": "Test", "generated": "true"}
        write_md_with_preserved_notes(md, fm, "auto content")
        text = md.read_text()
        assert "auto content" in text
        assert "---" in text

    def test_notes_preserved(self, tmp_path):
        md = tmp_path / "talk" / "index.md"
        fm = {"title": "Test", "generated": "true"}

        # First write
        write_md_with_preserved_notes(md, fm, "v1")
        # Simulate user editing notes
        text = md.read_text()
        text = text.replace("(2026 talks.)", "My custom notes")
        md.write_text(text)

        # Re-generate
        write_md_with_preserved_notes(md, fm, "v2")
        text = md.read_text()
        assert "My custom notes" in text
        assert "v2" in text
        assert "v1" not in text


# ── Integration: full build output ──────────────────────────────────────


class TestWriteIndices:
    def test_creates_expected_files(self, tmp_path):
        talks = [
            _make_talk(status="Scheduled", talk_id="upcoming1"),
            _make_talk(status="Completed", talk_id="past1", talk_date=date(2025, 6, 1)),
        ]
        write_indices(tmp_path, talks)

        assert (tmp_path / "index.md").exists()
        assert (tmp_path / "past" / "index.md").exists()
        assert (tmp_path / "tags" / "index.md").exists()
        assert (tmp_path / "types" / "index.md").exists()

    def test_index_has_stats(self, tmp_path):
        talks = [_make_talk()]
        write_indices(tmp_path, talks)
        text = (tmp_path / "index.md").read_text()
        assert "stats-bar" in text

    def test_past_has_map(self, tmp_path):
        talks = [
            _make_talk(status="Completed", city="Phoenix"),
        ]
        write_indices(tmp_path, talks)
        text = (tmp_path / "past" / "index.md").read_text()
        assert "world-map" in text

    def test_tag_pages_created(self, tmp_path):
        talks = [_make_talk(tags=["ml", "astro"])]
        write_indices(tmp_path, talks)
        assert (tmp_path / "tags" / "ml" / "index.md").exists()
        assert (tmp_path / "tags" / "astro" / "index.md").exists()

    def test_type_pages_created(self, tmp_path):
        talks = [_make_talk(talk_type="Oral")]
        write_indices(tmp_path, talks)
        assert (tmp_path / "types" / "oral" / "index.md").exists()

    def test_chip_cloud_on_tags_index(self, tmp_path):
        talks = [_make_talk()]
        write_indices(tmp_path, talks)
        text = (tmp_path / "tags" / "index.md").read_text()
        assert "chip-cloud" in text


# ── CSS validation ──────────────────────────────────────────────────────


class TestCSSIntegrity:
    @pytest.fixture
    def css(self):
        css_path = Path(__file__).resolve().parent.parent / "assets" / "style.css"
        return css_path.read_text()

    def test_dark_mode_exists(self, css):
        assert "@media (prefers-color-scheme: dark)" in css

    def test_all_root_vars_overridden_in_dark(self, css):
        """Every custom property in :root should be overridden in dark mode."""
        import re

        # Extract light-mode vars
        root_match = re.search(r":root\s*\{([^}]+)\}", css)
        assert root_match
        light_vars = set(re.findall(r"(--[\w-]+):", root_match.group(1)))

        # Extract dark-mode vars
        dark_match = re.search(
            r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{[^{]*:root\s*\{([^}]+)\}",
            css,
        )
        assert dark_match
        dark_vars = set(re.findall(r"(--[\w-]+):", dark_match.group(1)))

        missing = light_vars - dark_vars
        assert missing == set(), f"CSS vars not overridden in dark mode: {missing}"

    def test_no_hardcoded_colors_outside_root(self, css):
        """No bare hex colors should appear outside :root and dark :root blocks.
        Exceptions: #fff (white text on colored bg) and rgba values."""
        import re

        # Remove :root blocks and dark mode :root
        stripped = re.sub(r":root\s*\{[^}]+\}", "", css)
        # Remove the dark media query wrapper line itself
        stripped = re.sub(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{", "", stripped)

        # Find hex colors (3-8 chars), excluding #fff/#ffffff
        hexes = re.findall(r"#([0-9a-fA-F]{3,8})\b", stripped)
        non_white = [h for h in hexes if h.lower() not in ("fff", "ffffff")]
        assert non_white == [], f"Hardcoded hex colors found outside :root: #{', #'.join(non_white)}"


# ── Template validation ─────────────────────────────────────────────────


class TestTemplate:
    @pytest.fixture
    def template(self):
        path = Path(__file__).resolve().parent.parent / "assets" / "template.html"
        return path.read_text()

    def test_has_nav_links(self, template):
        assert "Home" in template
        assert "Past" in template
        assert "Tags" in template
        assert "Types" in template

    def test_has_site_title(self, template):
        assert "Talks &amp; Engagements" in template

    def test_has_viewport_meta(self, template):
        assert "viewport" in template

    def test_has_css_link(self, template):
        assert "style.css" in template
