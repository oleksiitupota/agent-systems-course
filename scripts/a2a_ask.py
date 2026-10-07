#!/usr/bin/env python3
"""Send one synchronous A2A 1.0 SendMessage to a peer and print its text reply.

The bundled OpenClaw A2A channel sends with returnImmediately=true, so the
caller never sees the answer. This helper waits for it instead.

Usage: python3 scripts/a2a_ask.py PEER "brief text"   (or the brief on stdin)
Env:   A2A_<PEER>_URL    e.g. http://openclaw-cto:18789/a2a/v1
       A2A_<PEER>_TOKEN  bearer token the peer gateway accepts
"""
import json
import os
import sys
import urllib.request
import uuid

TIMEOUT_S = 600


def texts(node):
    """Collect text parts from a task's status message and artifacts."""
    status = (node.get("status") or {}).get("message") or {}
    parts = list(status.get("parts") or [])
    for artifact in node.get("artifacts") or []:
        parts += artifact.get("parts") or []
    return [p["text"] for p in parts if isinstance(p, dict) and p.get("text")]


def ask(peer, text):
    key = peer.upper().replace("-", "_")
    url, token = os.environ[f"A2A_{key}_URL"], os.environ[f"A2A_{key}_TOKEN"]
    body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "SendMessage",
        "params": {
            "message": {"messageId": str(uuid.uuid4()), "role": "ROLE_USER", "parts": [{"text": text}]},
            "configuration": {"returnImmediately": False},
        },
    }
    request = urllib.request.Request(url, json.dumps(body).encode(), {
        "content-type": "application/json", "authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        reply = json.load(response)
    if reply.get("error"):
        raise RuntimeError(f"A2A error {reply['error'].get('code')}: {reply['error'].get('message')}")
    result = reply.get("result") or {}
    task = result.get("task") or result
    state = (task.get("status") or {}).get("state", "")
    answer = "\n\n".join(texts(task))
    if "FAILED" in state.upper() or not answer:
        raise RuntimeError(f"peer {peer} returned state={state or 'unknown'} without an answer")
    return answer


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    brief = sys.argv[2] if len(sys.argv) == 3 else sys.stdin.read()
    try:
        print(ask(sys.argv[1], brief))
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        sys.exit(f"a2a_ask failed: {error}")
