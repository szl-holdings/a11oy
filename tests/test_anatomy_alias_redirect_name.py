"""GET /anatomy must not NameError RedirectResponse.

serve.py imports RedirectResponse as _PTG_Redirect. The alias handler
has to call _PTG_Redirect, not the unbound name RedirectResponse.
GET /anatomy/ already 302s via the mounted sub-app; bare /anatomy 500s.
"""
from pathlib import Path

SERVE = Path(__file__).resolve().parents[1] / "serve.py"


def test_anatomy_alias_uses_ptg_redirect() -> None:
    text = SERVE.read_text(encoding="utf-8")
    assert "async def _anatomy_alias():" in text
    assert "return _PTG_Redirect(\"/living-anatomy\", status_code=302)" in text
    assert "return RedirectResponse(\"/living-anatomy\", status_code=302)" not in text
