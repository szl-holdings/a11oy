# a11oy /uds tab — ADDITIVE integration note

Adds a `/uds` route to the a11oy HF Space showing the 5 bundles + deploy instructions.
**ADDITIVE only** — does not modify or remove any existing a11oy route or tab.

## Drop-in (FastAPI Space)
1. Add `uds.html` to the Space root.
2. Add a route in the existing app module (do NOT replace existing routes):
   ```python
   from fastapi.responses import FileResponse
   @app.get("/uds")
   def uds_tab():
       return FileResponse("uds.html")
   ```
3. **PURIQ gotcha:** a11oy's Dockerfile uses explicit per-file `COPY` (not `COPY . .`).
   Add a line so the asset enters the image:
   ```dockerfile
   COPY uds.html ./uds.html
   ```
   If you put the route in a new `.py`, add its `COPY` line too.
4. Link it from the nav: add `<a href="/uds">UDS</a>` next to the existing tabs.

## Verify after deploy
```bash
curl -sL -o /dev/null -w "%{http_code}\n" https://<a11oy-space>/uds   # expect 200
```

This patch was NOT applied to the live Space in this session (the live-Space edit is a
separate surface task); it is staged here ready for the a11oy Space maintainer to apply
without risk to existing tabs.
