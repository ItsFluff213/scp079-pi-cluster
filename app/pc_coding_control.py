#!/usr/bin/env python3
"""Small Windows companion controlled by relay_control.py."""
from __future__ import annotations
import json, os, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.getenv("CODING_CONTROL_HOST", "0.0.0.0")
PORT = int(os.getenv("CODING_CONTROL_PORT", "8091"))
TOKEN = os.getenv("CODING_CONTROL_TOKEN", "")
PROJECT = os.path.abspath(os.getenv("CODING_PROJECT", os.path.expanduser("~/Documents/scp079-coding")))
MODEL = os.getenv("CODING_MODEL", "ollama/qwen2.5-coder:7b")
OLLAMA_BASE = os.getenv("OLLAMA_API_BASE", "http://dsam:11434")
proc: subprocess.Popen[bytes] | None = None

class Handler(BaseHTTPRequestHandler):
    def out(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def ok(self) -> bool:
        return not TOKEN or self.headers.get("Authorization", "") == f"Bearer {TOKEN}"
    def do_GET(self) -> None:
        if not self.ok(): self.out(401, {"error":"unauthorized"}); return
        running = proc is not None and proc.poll() is None
        self.out(200, {"running": running, "project": PROJECT, "model": MODEL})
    def do_POST(self) -> None:
        global proc
        if not self.ok(): self.out(401, {"error":"unauthorized"}); return
        action = self.path.rstrip("/").split("/")[-1]
        if action == "start":
            if proc is not None and proc.poll() is None: self.out(200, {"running":True,"already":True}); return
            os.makedirs(PROJECT, exist_ok=True)
            env = os.environ.copy(); env["OLLAMA_API_BASE"] = OLLAMA_BASE
            proc = subprocess.Popen(["aider", "--model", MODEL], cwd=PROJECT, env=env, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
            self.out(200, {"running":True,"pid":proc.pid}); return
        if action == "stop":
            if proc is not None and proc.poll() is None:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
            proc = None; self.out(200, {"running":False}); return
        self.out(404, {"error":"use /start or /stop"})
    def log_message(self, fmt: str, *args: object) -> None: print("coding-control:", fmt % args, flush=True)

if __name__ == "__main__":
    print(f"coding control listening on {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
