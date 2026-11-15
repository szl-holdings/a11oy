import argparse, json, os
from http.server import BaseHTTPRequestHandler, HTTPServer

"""Read-only anatomy projection server (front end + back end, stdlib only).

Routes:
  GET /healthz                          -> liveness + doctrine version
  GET /v1/models                        -> list of passports served
  GET /v1/models/{model_id}/anatomy     -> full passport JSON
  GET /v1/passports/{digest}            -> passport by content digest
  GET /v1/models/{model_id}/promotion   -> promotion decision (computed live)
Passports are read from a directory of *.passport.json files. The server
is read-only and stateless: it never mutates passports, it only projects them.
"""
from .promotion import evaluate
from .verifier import verify

def load_passports(directory):
    out = {}
    for fn in os.listdir(directory):
        if fn.endswith(".passport.json"):
            p = json.load(open(os.path.join(directory, fn), encoding="utf-8"))
            out[p["model_id"]] = p
    return out

class Handler(BaseHTTPRequestHandler):
    passports = {}
    def do_GET(self):
        parts = [p for p in self.path.split("/") if p]
        try:
            if parts == ["healthz"]:
                body = {"status": "ok", "service": "ouroboros-passport/0.1", "doctrine": "MEASURED/UNKNOWN/ABSTAIN"}
            elif parts == ["v1", "models"]:
                body = {"models": sorted(self.passports)}
            elif len(parts) == 4 and parts[:2] == ["v1", "models"] and parts[3] == "anatomy":
                p = self.passports.get(parts[2])
                if not p:
                    return self._json(404, {"error": "not found"})
                body = {"passport": p, "verification": verify(p)}
            elif len(parts) == 4 and parts[:2] == ["v1", "models"] and parts[3] == "promotion":
                p = self.passports.get(parts[2])
                if not p:
                    return self._json(404, {"error": "not found"})
                body = evaluate(p)
            elif len(parts) == 3 and parts[:2] == ["v1", "passports"]:
                match = [p for p in self.passports.values() if p.get("digest") == parts[2]]
                body = match[0] if match else {"error": "not found"}
                if not match:
                    return self._json(404, body)
            else:
                return self._json(404, {"error": "unknown route"})
            return self._json(200, body)
        except Exception as e:
            return self._json(500, {"error": str(e)})
    def _json(self, code, body):
        data = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *a):
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    Handler.passports = load_passports(args.dir)
    print("serving", len(Handler.passports), "passports on port", args.port)
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()

if __name__ == "__main__":
    main()
