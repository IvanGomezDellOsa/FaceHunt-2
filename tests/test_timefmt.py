from app.utils.timefmt import format_range, format_timestamp, youtube_url_with_time


def test_format_timestamp_basic():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(5) == "00:05"
    assert format_timestamp(75) == "01:15"


def test_format_timestamp_hours():
    assert format_timestamp(3661) == "1:01:01"


def test_format_timestamp_negative_clamped():
    assert format_timestamp(-10) == "00:00"


def test_format_range_single_instant():
    assert format_range(30, 30) == "00:30"


def test_format_range_span():
    assert format_range(83, 105) == "01:23 – 01:45"


def test_youtube_url_adds_time():
    assert youtube_url_with_time("https://youtu.be/abc", 75) == "https://youtu.be/abc?t=75"


def test_youtube_url_replaces_existing_time():
    out = youtube_url_with_time("https://youtu.be/abc?t=10", 90)
    assert "t=90" in out and "t=10" not in out


def test_youtube_url_preserves_other_params():
    out = youtube_url_with_time("https://www.youtube.com/watch?v=xyz", 42)
    assert "v=xyz" in out and "t=42" in out
