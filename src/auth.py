"""Test-only signed, expiring authority; not production authentication."""
import base64
import hashlib
import hmac
import json
import os
import time


class AuthenticationError(Exception):
    pass


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class LabAuthority:
    """Random in-process signer; HTTP never issues credentials."""

    def __init__(self, secret=None):
        self._secret = os.urandom(32) if secret is None else secret
        if not isinstance(self._secret, bytes) or len(self._secret) < 32:
            raise ValueError("32-byte key required")

    def issue_for_test(self, principal, tenant, scopes, *, expires_in=300, now=None):
        issued = int(time.time() if now is None else now)
        claims = {"iss": "atlas-local-fixture", "sub": principal, "tenant": tenant,
                  "scopes": scopes, "exp": issued + expires_in}
        body = _b64(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
        signature = _b64(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())
        return f"{body}.{signature}"

    def verify(self, authorization, required_scope, now=None):
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise AuthenticationError("missing bearer token")
        try:
            body, signature = authorization[7:].split(".")
            if len(body) > 4096:
                raise ValueError("too long")
            actual = _b64(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(actual, signature):
                raise AuthenticationError("invalid signature")
            raw = base64.b64decode(body + "=" * (-len(body) % 4), altchars=b"-_", validate=True)
            claims = json.loads(raw)
            now = int(time.time() if now is None else now)
            if (not isinstance(claims, dict) or claims.get("iss") != "atlas-local-fixture"
                    or not isinstance(claims.get("sub"), str) or not claims["sub"]
                    or not isinstance(claims.get("tenant"), str) or not claims["tenant"]
                    or type(claims.get("exp")) is not int or claims["exp"] <= now
                    or not isinstance(claims.get("scopes"), list)
                    or not all(isinstance(scope, str) for scope in claims["scopes"])
                    or required_scope not in claims["scopes"]):
                raise AuthenticationError("invalid authority")
            return {"principal": claims["sub"], "tenant": claims["tenant"]}
        except (ValueError, UnicodeError, TypeError, base64.binascii.Error) as exc:
            raise AuthenticationError("malformed authority") from exc
