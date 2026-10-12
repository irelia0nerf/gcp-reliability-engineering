"""Loopback-only synthetic Atlas HTTP API with signed test identities."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from src.atlas import Atlas, Conflict, Forbidden, Unavailable
from src.auth import AuthenticationError, LabAuthority


def no_duplicate_keys(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Avoid logging Authorization headers in this lab.

    def respond(self, code, body):
        raw = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def identity(self, scope):
        return self.server.authority.verify(self.headers.get("Authorization"), scope)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health/live":
            return self.respond(200, {"live": True, "scope": "process"})
        if path == "/health/ready":
            try:
                self.server.store.snapshot()
                return self.respond(200, {"ready": True, "scope": "local_sqlite"})
            except Exception:
                return self.respond(503, {"ready": False})
        if not path.startswith("/v1/jobs/") or len(path.split("/")) != 4:
            return self.respond(404, {"error": "not_found"})
        try:
            actor = self.identity("jobs:read")
            data = self.server.store.get(actor["tenant"], path.split("/")[-1])
            return self.respond(200, data)
        except AuthenticationError:
            return self.respond(401, {"error": "unauthorized"})
        except Forbidden:
            return self.respond(404, {"error": "not_found"})
        except Exception:
            return self.respond(503, {"error": "dependency_unavailable"})

    def do_POST(self):
        if urlsplit(self.path).path != "/v1/jobs":
            return self.respond(404, {"error": "not_found"})
        try:
            actor = self.identity("jobs:create")
        except AuthenticationError:
            return self.respond(401, {"error": "unauthorized"})
        size = self.headers.get("Content-Length", "")
        if (self.headers.get("Transfer-Encoding") or not size.isascii() or
                not size.isdecimal() or not 0 < int(size) <= 4096):
            return self.respond(400, {"error": "invalid_length"})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.respond(415, {"error": "unsupported_media_type"})
        key = self.headers.get("Idempotency-Key", "")
        if not 1 <= len(key) <= 128 or not key.isascii() or not key.isprintable():
            return self.respond(400, {"error": "invalid_idempotency_key"})
        try:
            body = json.loads(self.rfile.read(int(size)), object_pairs_hook=no_duplicate_keys)
            if (not isinstance(body, dict) or set(body) != {"value"}
                    or type(body["value"]) is not int or not -1000000 <= body["value"] <= 1000000):
                raise ValueError("invalid payload")
            job = self.server.store.admit(actor["tenant"], key, body["value"])
            return self.respond(202, job)
        except (ValueError, UnicodeDecodeError):
            return self.respond(400, {"error": "invalid_payload"})
        except Conflict:
            return self.respond(409, {"error": "idempotency_conflict"})
        except Unavailable:
            return self.respond(503, {"error": "dependency_unavailable"})
        except Exception:
            return self.respond(503, {"error": "dependency_unavailable"})

def make_server(store, authority, host="127.0.0.1", port=0):
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError("bind only to loopback for local fixture")
    server = ThreadingHTTPServer((host, port), Handler)
    server.store, server.authority = store, authority
    return server

def main():
    store = Atlas(os.environ.get("ATLAS_DB", "./atlas.db"))
    server = make_server(store, LabAuthority(), port=int(os.environ.get("PORT", "8080")))
    print("Local-only fixture: no HTTP token issuance", flush=True)
    server.serve_forever()

if __name__ == "__main__":
    main()
