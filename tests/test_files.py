from app.utils.files import human_size, sanitize_filename


def test_sanitize_basic_ascii():
    assert sanitize_filename("Hello World") == "Hello World"


def test_sanitize_transliterates_accents():
    assert sanitize_filename("Café") == "Cafe"


def test_sanitize_replaces_prohibited():
    out = sanitize_filename('a/b:c*d?')
    for ch in '/:*?':
        assert ch not in out


def test_sanitize_empty_uses_fallback():
    assert sanitize_filename("   ") == "video"
    assert sanitize_filename("", fallback="x") == "x"


def test_sanitize_truncates_length():
    assert len(sanitize_filename("a" * 500, max_len=100)) == 100


def test_human_size():
    assert human_size(512) == "512.0 B"
    assert human_size(1536) == "1.5 KB"
    assert human_size(1048576) == "1.0 MB"
