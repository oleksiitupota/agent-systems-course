"""Check scripts/a2a_ask.py against a local fake A2A peer."""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).with_name("a2a_ask.py")
seen = {}


class Peer(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        seen.update(auth=self.headers["authorization"], body=body)
        text = body["params"]["message"]["parts"][0]["text"]
        if text == "fail":
            result = {"task": {"id": "t2", "status": {"state": "TASK_STATE_FAILED"}}}
        else:
            result = {"task": {"id": "t1", "status": {"state": "TASK_STATE_COMPLETED"},
                               "artifacts": [{"parts": [{"text": "echo: " + text}]}]}}
        data = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def run(text):
    server = HTTPServer(("127.0.0.1", 0), Peer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {**os.environ, "A2A_CTO_URL": f"http://127.0.0.1:{server.server_port}/a2a/v1", "A2A_CTO_TOKEN": "secret"}
    try:
        return subprocess.run([sys.executable, SCRIPT, "cto", text], env=env, capture_output=True, text=True)
    finally:
        server.shutdown()


if __name__ == "__main__":
    ok = run("ISTL-1 impact")
    assert ok.returncode == 0 and ok.stdout.strip() == "echo: ISTL-1 impact", ok
    assert seen["auth"] == "Bearer secret"
    assert seen["body"]["method"] == "SendMessage"
    assert seen["body"]["params"]["configuration"]["returnImmediately"] is False
    failed = run("fail")
    assert failed.returncode != 0 and "TASK_STATE_FAILED" in failed.stderr, failed
    print("a2a_ask: ok")
