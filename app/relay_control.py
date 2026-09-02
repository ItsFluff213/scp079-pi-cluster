#!/usr/bin/env python3
"""Allow-listed Pi-3 orchestration API for the SCP-079 cluster."""
from __future__ import annotations
import html, json, os, shlex, subprocess
from urllib.request import Request, urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = os.getenv("CONTROL_HOST", "0.0.0.0")
PORT = int(os.getenv("CONTROL_PORT", "8090"))
TOKEN = os.getenv("CONTROL_TOKEN", os.getenv("SCP079_API_TOKEN", ""))
SSH_KEY = os.getenv("CONTROL_SSH_KEY", "/home/admin-relay/.ssh/scp079_cluster")
CODING_URL = os.getenv("CODING_CONTROL_URL", "").rstrip("/")
CODING_TOKEN = os.getenv("CODING_CONTROL_TOKEN", TOKEN)
SERVICES = {
    "dashboard": ("logic", os.getenv("LOGIC_USER", "admin"), "scp079-voice-core.service"),
    "scp079": ("logic", os.getenv("LOGIC_USER", "admin"), "scp079-voice-core.service"),
    "so100": ("dsam", os.getenv("DSAM_USER", "felix"), "so100-webctl.service"),
    "coding": ("local", "", os.getenv("CODING_SERVICE", "scp079-coding-agent.service")),
    "swarm": ("local", "", "docker.service"),
}

def auth(h: BaseHTTPRequestHandler) -> bool:
    return not TOKEN or h.headers.get("Authorization", "") == f"Bearer {TOKEN}"

def unit(name: str, action: str) -> tuple[int, str]:
    if name not in SERVICES or action not in {"start", "stop", "restart", "status"}:
        return 400, "unknown service or action"
    if name == "coding" and CODING_URL:
        try:
            req = Request(f"{CODING_URL}/{action}", method="POST", headers={"Authorization": f"Bearer {CODING_TOKEN}"} if CODING_TOKEN else {})
            with urlopen(req, timeout=10) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except Exception as exc:
            return 502, str(exc)
    host, user, service = SERVICES[name]
    if host == "local":
        cmd = ["systemctl", action, service]
    else:
        remote = f"sudo systemctl {shlex.quote(action)} {shlex.quote(service)}"
        cmd = ["ssh", "-i", SSH_KEY, "-o", "BatchMode=yes", f"{user}@{host}", remote]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        return (200 if p.returncode == 0 else 502), (p.stdout + p.stderr).strip()[-4000:]
    except (OSError, subprocess.TimeoutExpired) as e:
        return 502, str(e)

class Handler(BaseHTTPRequestHandler):
    def send_body(self, code: int, body: str, kind: str = "application/json") -> None:
        raw = body.encode(); self.send_response(code); self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self) -> None:
        if not auth(self): self.send_body(401, json.dumps({"error":"unauthorized"})); return
        path = urlparse(self.path).path
        if path in {"/", "/ui/"}:
            rows = "".join(f"<tr><td>{html.escape(n)}</td><td><form method='post' action='/api/services/{n}/start'><button>Start</button></form></td><td><form method='post' action='/api/services/{n}/stop'><button>Stop</button></form></td><td><form method='post' action='/api/services/{n}/status'><button>Status</button></form></td></tr>" for n in SERVICES)
            page = "<!doctype html><meta charset='utf-8'><title>SCP-079 Control</title><style>body{background:#090b0d;color:#d6e7e8;font:16px monospace;margin:2rem}table{border-collapse:collapse}td{padding:8px;border-bottom:1px solid #354}button{font:inherit;background:#182b2d;color:#d6e7e8;border:1px solid #5aa;padding:5px 12px}</style><h1>SCP-079 // CONTROL NODE</h1><p>Pi 3 orchestration console</p><table><tr><th>Service</th><th colspan=3>Action</th></tr>" + rows + "</table>"
            self.send_body(200, page, "text/html; charset=utf-8"); return
        if path == "/health": self.send_body(200, json.dumps({"ok":True,"node":"relay","services":list(SERVICES)})); return
        if path == "/api/services": self.send_body(200, json.dumps({n:unit(n,"status")[1] for n in SERVICES})); return
        self.send_body(404, json.dumps({"error":"not found"}))
    def do_POST(self) -> None:
        if not auth(self): self.send_body(401, json.dumps({"error":"unauthorized"})); return
        p = [x for x in urlparse(self.path).path.split("/") if x]
        if len(p) == 4 and p[:2] == ["api", "services"]:
            code, out = unit(p[2], p[3]); self.send_body(code, json.dumps({"service":p[2],"action":p[3],"output":out})); return
        self.send_body(404, json.dumps({"error":"not found"}))
    def log_message(self, fmt: str, *args: object) -> None: print("control:", fmt % args, flush=True)

if __name__ == "__main__":
    print(f"SCP-079 control listening on {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
