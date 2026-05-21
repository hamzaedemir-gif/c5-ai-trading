"""Smoke checks for the hot-reload dev tooling.

We don't actually launch uvicorn or vite here -- spawning a real reloading
server in CI is fragile. We just verify that the scripts exist, point at
the right entry points, and would invoke the right commands.
"""
import json
import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_package_json_has_dev_all():
    pkg = json.loads((ROOT / "package.json").read_text())
    scripts = pkg.get("scripts", {})
    assert "dev:all" in scripts
    # backend launcher must use uvicorn --factory --reload
    backend = scripts.get("dev:backend", "")
    assert "uvicorn" in backend
    assert "--factory" in backend
    assert "--reload" in backend
    assert "api.app:create_app" in backend
    # frontend launcher must invoke the frontend workspace
    assert "frontend" in scripts.get("dev:frontend", "")
    # concurrently must be a declared devDependency so npm install grabs it
    assert "concurrently" in pkg.get("devDependencies", {})


def test_dev_sh_is_executable():
    sh = ROOT / "dev.sh"
    assert sh.is_file()
    mode = sh.stat().st_mode
    assert mode & stat.S_IXUSR, "dev.sh must be chmod +x"
    body = sh.read_text()
    # dev.sh must NOT force demo mode any more -- the app auto-detects from
    # .env so that ./setup-keys.sh -> ./dev.sh gives the user live data
    # without further configuration.
    assert "export C5_DEMO_MODE=1" not in body
    assert "C5_TRADING_MODE" in body and "paper" in body
    assert "npm run dev:all" in body
    assert "http://localhost:5173" in body
    # mentions setup-keys so users see the upgrade path
    assert "setup-keys" in body


def test_dev_ps1_exists_and_mentions_setup_keys():
    ps1 = ROOT / "dev.ps1"
    assert ps1.is_file()
    body = ps1.read_text()
    # Same contract as dev.sh: do not force demo mode.
    assert '$env:C5_DEMO_MODE     = "1"' not in body
    assert '$env:C5_DEMO_MODE = "1"' not in body
    assert "npm run dev:all" in body
    assert "http://localhost:5173" in body
    # checks for prereqs explicitly
    assert "python" in body.lower()
    assert "npm" in body.lower()
    # points users at the new setup-keys workflow
    assert "setup-keys" in body


def test_makefile_has_dev_target():
    mk = (ROOT / "Makefile").read_text()
    assert "\ndev:" in mk
    assert "./dev.sh" in mk
    # Don't lose the production path either.
    assert "docker-up" in mk or "docker compose" in mk
