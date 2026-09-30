"""Bind serve.RedirectResponse to serve._PTG_Redirect.

serve.py imports RedirectResponse as _PTG_Redirect, then _anatomy_alias
calls the unbound name. Importing this after that alias exists makes
bare GET /anatomy 302 onto /living-anatomy. GET /anatomy/ already works.
"""
from __future__ import annotations

import sys


def bind_ptg_redirect() -> bool:
    for name in ("serve", "__main__"):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "_PTG_Redirect"):
            setattr(mod, "RedirectResponse", getattr(mod, "_PTG_Redirect"))
            return True
    return False


bind_ptg_redirect()
