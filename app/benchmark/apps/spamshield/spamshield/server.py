"""Milter-style HTTP endpoint used by the Postfix gateway (mTLS, client certificate required)."""

from __future__ import annotations

import logging
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

import yaml

from .classifier import SpamClassifier, message_ref
from .quarantine import Quarantine
from .ratelimit import TokenBucket

log = logging.getLogger("spamshield")


def build(cfg):
    clf = SpamClassifier(cfg["model_path"], cfg["thresholds"]["tag"], cfg["thresholds"]["quarantine"])
    q = Quarantine(cfg["quarantine"]["path"])
    bucket = TokenBucket(cfg["rate_limit"]["requests_per_minute"])

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/v1/classify":
                self.send_error(404)
                return
            if not bucket.take(self.client_address[0]):
                self.send_error(429)
                return
            msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            v = clf.classify(msg.get("subject", ""), msg.get("body", ""))
            if v.action == "quarantine":
                q.store(msg)
            log.info("classified message=%s action=%s p=%.3f model_version=%s",
                     message_ref(msg["message_id"]), v.action, v.spam_probability, v.model_version)
            body = json.dumps({"action": v.action, "score": round(v.spam_probability, 3)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main(config_path: str = "config/spamshield.yaml"):
    cfg = yaml.safe_load(open(config_path))
    server = ThreadingHTTPServer(("0.0.0.0", cfg["port"]), build(cfg))
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cfg["tls"]["cert"], cfg["tls"]["key"])
    ctx.load_verify_locations(cfg["tls"]["client_ca"])
    ctx.verify_mode = ssl.CERT_REQUIRED  # only the mail gateway's client certificate is accepted
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
