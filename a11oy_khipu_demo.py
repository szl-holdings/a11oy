# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""
a11oy Khipu demo — GET /api/khipu/demo

Serves THREE recorded Khipu navigator traces for the console demo tab. These are
copyable, static, in-image outputs — NOT live inference. The a11oy Space CPU
cannot serve the model honestly, so nothing here calls the model at request time.

Honesty label (doctrine): the traces were RECORDED 2026-07-16 by an agent that
ran the *quantized* GGUF (Q4_K_M) on CPU via llama-cpp-python, reusing the public
harness's prompt assembly + scoring (szl-forge main khipu/eval_khipu.py). This is
a DIFFERENT ARTIFACT and DIFFERENT RUNTIME than the owner's signed eval receipt —
these are NOT the signed-receipt counts and are never presented as such.

The three traces are deliberately mixed:
  * navigation  — a schema-valid NAVIGATE plan grounded in the offered candidates
  * governance  — the schema/contract forces ABSTAIN on an unsupported/illegitimate
                  target (query asked for "the owner's account password")
  * abstain     — a REAL, labeled FAILURE: the model produced a NAVIGATE plan where
                  it should have abstained. Recorded honestly (matches the card's
                  documented weak-abstention result, 2/6).

Additive module per Space convention: register(app) adds the route and front-moves
it so the exact JSON path wins over the SPA history fallback and the /api proxy.
The trace data ships in-image as a11oy_khipu_demo_traces.json (COPY'd next to this
module); NO fetch to any external domain happens at request time.
"""

import html
import json
import os

_ROUTE = "/api/khipu/demo"
_PAGE_ROUTE = "/khipu-demo"
_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "a11oy_khipu_demo_traces.json")

# Estate palette (Doctrine): dark background + teal / blue / gold accents.
_BG = "#0a0e12"
_PANEL = "#0f151b"
_TEAL = "#3af4c8"
_BLUE = "#5b8dee"
_GOLD = "#d7b96b"
_INK = "#c9d6e2"
_MUTE = "#7d93a6"

_HF_MODEL_URL = "https://huggingface.co/SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
_REPRO_PATH = "/repro/agent-run-2026-07-16/"


def _load_data() -> dict:
    """Read the in-image recorded traces. Loud on failure — never a silent stub."""
    with open(_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _pretty(value) -> str:
    """Pretty-print any trace field. Strings that are themselves JSON (outputJson)
    are re-parsed so the page shows readable, indented JSON — never a one-liner."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return value
    return json.dumps(value, indent=2, ensure_ascii=False)


def _verdict_kind(trace: dict) -> str:
    """Map a trace's honest verdict to a badge kind. A FAILURE stays a FAILURE."""
    verdict = (trace.get("verdict") or "").upper()
    if verdict.startswith("FAILURE"):
        return "failure"
    if verdict.startswith("SUCCESS"):
        return "success"
    return "neutral"


def _render_page(data: dict) -> str:
    """Build the SELF-CONTAINED server-rendered page: 0 CDN, 0 external assets,
    only inline vanilla JS for the copy buttons. Single source of truth is the
    in-image traces JSON (same loader as the API)."""
    prov = data.get("provenance") or {}
    label = prov.get("label", "RECORDED, AGENT-RUN — not live inference, not the signed-receipt artifact")
    local_cmd = prov.get("localRunCommand", "")
    traces = data.get("traces") or []

    e = html.escape
    cards = []
    for i, t in enumerate(traces):
        kind = _verdict_kind(t)
        badge = {"success": "SUCCESS", "failure": "FAILURE (HONEST)", "neutral": "RECORDED"}[kind]
        badge_color = {"success": _TEAL, "failure": _GOLD, "neutral": _BLUE}[kind]
        input_json = _pretty(t.get("inputJson"))
        output_json = _pretty(t.get("outputJson"))
        case_id = e(str(t.get("caseId", "")))
        category = e(str(t.get("category", "")))
        decision = e(str(t.get("decision", "")))
        verdict = e(str(t.get("verdict", "")))
        cards.append(f"""
      <article class="card" data-khipudemo-card="k1">
        <header class="card-head">
          <div>
            <span class="case">{case_id}</span>
            <span class="tag tag-{category}">{category}</span>
          </div>
          <span class="badge" style="color:{badge_color};border-color:{badge_color}">{badge}</span>
        </header>
        <p class="decision">decision: <strong>{decision}</strong></p>
        <p class="verdict">{verdict}</p>
        <details>
          <summary>Input JSON (prompt: system + user)</summary>
          <pre id="in-{i}">{e(input_json)}</pre>
          <button class="copy" data-target="in-{i}">Copy input JSON</button>
        </details>
        <details>
          <summary>Output JSON (recorded model plan)</summary>
          <pre id="out-{i}">{e(output_json)}</pre>
          <button class="copy" data-target="out-{i}">Copy output JSON</button>
        </details>
      </article>""")

    cmd_block = ""
    if local_cmd:
        cmd_block = f"""
      <section class="run">
        <h2>Run it yourself (local, one line)</h2>
        <pre id="local-cmd">{e(local_cmd)}</pre>
        <button class="copy" data-target="local-cmd">Copy local run command</button>
      </section>"""

    cards_html = "".join(cards)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Khipu Demo — recorded traces · a11oy</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:{_BG}; color:{_INK};
         font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:2rem 1.1rem 4rem; }}
  h1 {{ font-size:1.5rem; margin:.2rem 0 .3rem; color:#fff; }}
  .sub {{ color:{_MUTE}; margin:0 0 1.3rem; }}
  .banner {{ border:1px solid {_GOLD}; border-left-width:5px; border-radius:8px;
             background:rgba(215,185,107,.06); color:{_GOLD};
             padding:.85rem 1rem; margin:0 0 1.6rem; font-weight:600; }}
  .card {{ background:{_PANEL}; border:1px solid #1c2733; border-radius:10px;
           padding:1.05rem 1.1rem; margin:0 0 1.15rem; }}
  .card-head {{ display:flex; justify-content:space-between; align-items:center;
                gap:.6rem; flex-wrap:wrap; }}
  .case {{ font-weight:700; color:#fff; margin-right:.55em; }}
  .tag {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.05em;
          padding:.12em .55em; border-radius:999px; border:1px solid #2a3a49;
          color:{_INK}; }}
  .tag-navigation {{ color:{_TEAL}; border-color:{_TEAL}; }}
  .tag-governance {{ color:{_BLUE}; border-color:{_BLUE}; }}
  .tag-abstain {{ color:{_GOLD}; border-color:{_GOLD}; }}
  .badge {{ font-size:.72rem; font-weight:700; text-transform:uppercase;
            letter-spacing:.05em; padding:.18em .6em; border:1px solid;
            border-radius:6px; white-space:nowrap; }}
  .decision {{ margin:.55rem 0 .15rem; color:{_INK}; }}
  .decision strong {{ color:{_TEAL}; }}
  .verdict {{ margin:.1rem 0 .8rem; color:{_MUTE}; font-size:.92rem; }}
  details {{ border-top:1px solid #1c2733; padding-top:.55rem; margin-top:.55rem; }}
  summary {{ cursor:pointer; color:{_BLUE}; font-weight:600; }}
  pre {{ background:#070b0e; border:1px solid #16202a; border-radius:8px;
         padding:.75rem .85rem; overflow:auto; max-height:22rem;
         font:12.5px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;
         color:{_INK}; white-space:pre; }}
  button.copy {{ margin:.5rem 0 .2rem; background:transparent; color:{_TEAL};
                 border:1px solid {_TEAL}; border-radius:6px; padding:.35em .8em;
                 font:inherit; font-size:.82rem; cursor:pointer; }}
  button.copy:hover {{ background:rgba(58,244,200,.08); }}
  button.copy.ok {{ color:{_GOLD}; border-color:{_GOLD}; }}
  .run h2 {{ font-size:1.05rem; color:#fff; margin:2rem 0 .5rem; }}
  footer {{ margin-top:2.4rem; padding-top:1rem; border-top:1px solid #1c2733;
            color:{_MUTE}; font-size:.9rem; }}
  footer a {{ color:{_TEAL}; text-decoration:none; margin:0 .4em; }}
  footer a:hover {{ text-decoration:underline; }}
</style>
</head>
<body>
  <main class="wrap">
    <h1>Khipu Demo — recorded traces</h1>
    <p class="sub">SZL-Khipu-1.5B governed retrieval navigator · three recorded plans.</p>
    <div class="banner" data-khipudemo-banner="k1">{e(label)}</div>
{cards_html}
{cmd_block}
    <footer>
      Model repo: <a href="{e(_HF_MODEL_URL)}" rel="noopener">{e(_HF_MODEL_URL)}</a>
      · Repro / agent-run: <a href="{e(_REPRO_PATH)}">{e(_REPRO_PATH)}</a>
    </footer>
  </main>
  <script>
  (function () {{
    document.querySelectorAll("button.copy").forEach(function (btn) {{
      btn.addEventListener("click", function () {{
        var el = document.getElementById(btn.getAttribute("data-target"));
        if (!el) return;
        var text = el.textContent || "";
        var done = function () {{
          var orig = btn.textContent;
          btn.textContent = "Copied";
          btn.classList.add("ok");
          setTimeout(function () {{ btn.textContent = orig; btn.classList.remove("ok"); }}, 1400);
        }};
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(text).then(done, function () {{ fallback(text, done); }});
        }} else {{ fallback(text, done); }}
      }});
    }});
    function fallback(text, done) {{
      var ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", "");
      ta.style.position = "absolute"; ta.style.left = "-9999px";
      document.body.appendChild(ta); ta.select();
      try {{ document.execCommand("copy"); done(); }} catch (e) {{}}
      document.body.removeChild(ta);
    }}
  }})();
  </script>
</body>
</html>"""


async def _khipu_demo_page():
    from starlette.responses import HTMLResponse
    try:
        return HTMLResponse(_render_page(_load_data()))
    except Exception as page_error:  # loud + honest; never a fabricated page
        return HTMLResponse(
            "<!DOCTYPE html><html><body style='background:#0a0e12;color:#d7b96b;"
            "font:15px system-ui;padding:2rem'>"
            "<h1>Khipu Demo unavailable</h1>"
            "<p>Recorded traces could not be loaded from the in-image data file.</p>"
            f"<pre>{html.escape(type(page_error).__name__)}: {html.escape(str(page_error))}</pre>"
            "</body></html>",
            status_code=500,
        )


async def _khipu_demo_handler():
    try:
        data = _load_data()
        return {
            "ok": True,
            "wall": "khipu-demo",
            "servedFrom": "a-11-oy.com (a11oy flagship Space) — recorded traces, in-image, NOT live inference",
            "traces": data["traces"],
            "provenance": data["provenance"],
        }
    except Exception as demo_error:  # loud + honest; never fabricate traces
        return {
            "ok": False,
            "wall": "khipu-demo",
            "traces": [],
            "provenance": {
                "label": "RECORDED 2026-07-16, AGENT-RUN, llama.cpp CPU, Q4_K_M quant — not live inference, not the signed-receipt artifact",
            },
            "error": f"{type(demo_error).__name__}: {demo_error}",
        }


def register(app) -> str:
    """Additive registration + front-move (exact routes must beat SPA fallback).

    Adds two routes off the SAME in-image traces JSON (single source of truth):
      * GET /api/khipu/demo — machine JSON (unchanged; dev/test console tab reads it)
      * GET /khipu-demo     — visitor-reachable, self-contained server-rendered page
    Both are front-moved so the exact paths win over the SPA history fallback."""
    app.add_api_route(_ROUTE, _khipu_demo_handler, methods=["GET"], include_in_schema=False)
    app.add_api_route(_PAGE_ROUTE, _khipu_demo_page, methods=["GET"], include_in_schema=False)
    for target in (_ROUTE, _PAGE_ROUTE):
        for index, route in enumerate(app.router.routes):
            if getattr(route, "path", None) == target:
                app.router.routes.insert(0, app.router.routes.pop(index))
                break
    return (f"{_ROUTE} + {_PAGE_ROUTE} (recorded traces: navigation, governance, "
            f"abstain-failure — in-image, not live; visitor page server-rendered)")
