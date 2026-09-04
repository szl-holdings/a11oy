# Route note for command_v2

Do not replace pages/console.html or web/elite_console.html.

Additive hook (serve.py, before the proxy catch-all):

```python
from fastapi.responses import FileResponse

@app.get("/command-v2")
def command_v2():
    return FileResponse("web/command_v2.html", media_type="text/html")
```

Keep `/command` on the elite skin until this is reviewed.
Optional flag later:

```python
if os.environ.get("A11OY_COMMAND_SKIN") == "v2":
    # serve v2 at /command
```

Files on this branch:
- web/command_v2.html
- docs/audits/2026-09-04-command-centre-audit.md
