#!/usr/bin/env python3
"""Local stand-in for a WeCom group-bot webhook.

    python scripts/wecom_stub.py --port 8099 --log /tmp/wecom_received.jsonl

Accepts the same JSON body a real bot receives, answers {"errcode":0}, and appends every
request to the log file so a drill can prove *what* would have been sent.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG_PATH = Path("/tmp/wecom_received.jsonl")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", "replace")
        record = {"received_at": datetime.now(timezone.utc).isoformat(), "path": self.path, "body": raw}
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        payload = json.dumps({"errcode": 0, "errmsg": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        print(f"[wecom-stub] {self.command} {self.path} {length}B -> 200", flush=True)

    def log_message(self, fmt: str, *args) -> None:  # silence default stderr noise
        return


def main() -> int:
    global LOG_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--log", default=str(LOG_PATH))
    args = ap.parse_args()
    LOG_PATH = Path(args.log)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"[wecom-stub] listening on :{args.port}, log -> {LOG_PATH}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
