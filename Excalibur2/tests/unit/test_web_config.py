"""Tests for web config log helpers."""

from pathlib import Path

from excalibur.server.web_config import combine_log_sections, tail_file


def test_tail_file_reads_recent_bytes(tmp_path: Path) -> None:
    """tail_file returns the end of a log file."""
    log_path = tmp_path / "router.log"
    log_path.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    tail = tail_file(log_path, max_bytes=12)

    assert "line 3" in tail
    assert "line 1" not in tail


def test_combine_log_sections_labels_both_sources(tmp_path: Path) -> None:
    """Combined log output includes both activity and router sections."""
    activity_log_path = tmp_path / "activity.log"
    router_log_path = tmp_path / "router.log"

    combined = combine_log_sections(
        '2026-07-04 [MESSAGE] {"text":"hello"}',
        "",
        activity_log_path,
        router_log_path,
    )

    assert "Excalibur activity" in combined
    assert "Claude Code Router" in combined
    assert "hello" in combined
    assert "No router log yet." in combined
