"""Mock authentication stub."""
from __future__ import annotations

from typing import Dict


def sign_in(email: str) -> Dict[str, object]:
    """Mock sign-in: accepts any email.

    # TODO: replace with real authentication (email magic link / OAuth /
    #        password) and a real user/session record.
    """
    email = (email or "").strip()
    ok = "@" in email and "." in email.split("@")[-1]
    return {"email": email, "ok": ok}
