from core.env_file import read_env_keys, update_env_file


def test_update_creates_file_when_missing(tmp_path):
    p = tmp_path / ".env"
    update_env_file(p, {"ALPACA_API_KEY": "abc", "FINNHUB_API_KEY": "xyz"})
    text = p.read_text()
    assert "ALPACA_API_KEY=abc" in text
    assert "FINNHUB_API_KEY=xyz" in text


def test_update_replaces_existing_key(tmp_path):
    p = tmp_path / ".env"
    p.write_text("FOO=1\nALPACA_API_KEY=old\nBAR=2\n")
    update_env_file(p, {"ALPACA_API_KEY": "new"})
    lines = p.read_text().splitlines()
    assert lines == ["FOO=1", "ALPACA_API_KEY=new", "BAR=2"]


def test_update_collapses_duplicates(tmp_path):
    p = tmp_path / ".env"
    p.write_text("ALPACA_API_KEY=a\nALPACA_API_KEY=b\nALPACA_API_KEY=c\n")
    update_env_file(p, {"ALPACA_API_KEY": "final"})
    text = p.read_text()
    assert text.count("ALPACA_API_KEY=") == 1
    assert "ALPACA_API_KEY=final" in text


def test_update_preserves_comments_and_blanks(tmp_path):
    p = tmp_path / ".env"
    p.write_text(
        "# Alpaca keys\n"
        "ALPACA_API_KEY=old\n"
        "\n"
        "# Finnhub\n"
        "FINNHUB_API_KEY=fh\n"
    )
    update_env_file(p, {"ALPACA_API_KEY": "new"})
    text = p.read_text()
    assert "# Alpaca keys" in text
    assert "# Finnhub" in text
    assert "ALPACA_API_KEY=new" in text
    assert "FINNHUB_API_KEY=fh" in text


def test_update_appends_new_keys_at_end(tmp_path):
    p = tmp_path / ".env"
    p.write_text("EXISTING=1\n")
    update_env_file(p, {"NEW_KEY": "value"})
    lines = p.read_text().splitlines()
    assert lines[0] == "EXISTING=1"
    assert lines[1] == "NEW_KEY=value"


def test_update_ignores_commented_match(tmp_path):
    """A commented-out KEY= must not satisfy the upsert."""
    p = tmp_path / ".env"
    p.write_text("# ALPACA_API_KEY=ignored\n")
    update_env_file(p, {"ALPACA_API_KEY": "real"})
    text = p.read_text()
    assert "# ALPACA_API_KEY=ignored" in text   # preserved
    assert "ALPACA_API_KEY=real" in text        # appended


def test_read_env_keys_parses_quoted_values(tmp_path):
    p = tmp_path / ".env"
    p.write_text('FOO="hello"\nBAR=\'world\'\nBAZ=plain\n# COMMENT=ignored\n')
    out = read_env_keys(p)
    assert out == {"FOO": "hello", "BAR": "world", "BAZ": "plain"}


def test_atomic_write_handles_no_trailing_newline(tmp_path):
    p = tmp_path / ".env"
    p.write_text("FOO=1")   # no trailing newline
    update_env_file(p, {"BAR": "2"})
    out = read_env_keys(p)
    assert out == {"FOO": "1", "BAR": "2"}
