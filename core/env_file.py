"""Idempotent .env file editor.

Used by setup-keys.* helpers to write API keys safely:
  - existing `KEY=...` lines are replaced in place
  - duplicate lines are collapsed to one
  - keys not yet in the file are appended at the end
  - comments and unrelated lines are preserved
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping


def read_env_keys(path: str | Path) -> dict[str, str]:
    """Parse a .env file into a {KEY: value} dict.

    Comments, blank lines, and lines without `=` are skipped. Surrounding
    quotes on values are stripped to match the way dotenv loads them.
    """
    p = Path(path)
    if not p.exists():
        return {}
    out: dict[str, str] = {}
    for line in p.read_text().splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        out[key] = value
    return out


def update_env_file(path: str | Path, updates: Mapping[str, str]) -> None:
    """Upsert each key=value pair into the .env file at `path`.

    Atomicity: the file is read, modified in memory, then written out via
    a tmp file + rename so a crash mid-write can never leave a half-file.
    """
    p = Path(path)
    if p.exists():
        original_text = p.read_text()
        lines = original_text.splitlines(keepends=False)
        trailing_nl = original_text.endswith("\n")
    else:
        lines = []
        trailing_nl = True

    seen: set[str] = set()
    out_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                if key not in seen:
                    out_lines.append(f"{key}={updates[key]}")
                    seen.add(key)
                # drop subsequent duplicates
                continue
        out_lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            out_lines.append(f"{key}={value}")

    text = "\n".join(out_lines)
    if trailing_nl and (not text or not text.endswith("\n")):
        text += "\n"

    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(p)
