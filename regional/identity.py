"""Verify Google-signed ID tokens; derive tenant from server-side allowlist only."""
import json
import os
from dataclasses import dataclass


class IdentityRejected(Exception):
    pass


@dataclass(frozen=True)
class Actor:
    email: str
    tenant: str | None
    scopes: frozenset[str]
    role: str


def verified_claims(token, audience):
    """Provider verifier, replaceable for offline tests. Fail closed."""
    if not audience:
        raise IdentityRejected("audience unconfigured")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token
        return id_token.verify_oauth2_token(token, Request(), audience=audience)
    except Exception as exc:
        raise IdentityRejected("token verification failed") from exc


class IdentityPolicy:
    def __init__(self, audience, callers, task_email, dispatcher_email, verifier=verified_claims):
        if not audience or not task_email or not dispatcher_email:
            raise ValueError("audience and service identities required")
        if task_email == dispatcher_email:
            raise ValueError("separate worker and dispatcher identities")
        if not isinstance(callers, dict):
            raise ValueError("caller map must be an object")
        self.audience = audience
        self.callers = callers
        self.task_email = task_email.lower()
        self.dispatcher_email = dispatcher_email.lower()
        self.verifier = verifier

    @classmethod
    def from_env(cls):
        return cls(
            os.environ["ATLAS_EXPECTED_AUDIENCE"],
            json.loads(os.environ.get("ATLAS_CALLERS_JSON", "{}")),
            os.environ["ATLAS_TASK_SERVICE_ACCOUNT"],
            os.environ["ATLAS_DISPATCH_SERVICE_ACCOUNT"],
        )

    def authorize(self, bearer, required_scope):
        if not isinstance(bearer, str) or not bearer.startswith("Bearer "):
            raise IdentityRejected("bearer required")
        token = bearer[7:]
        if not token or len(token) > 8192 or " " in token:
            raise IdentityRejected("malformed bearer")
        try:
            claims = self.verifier(token, self.audience)
        except IdentityRejected:
            raise
        except Exception as exc:
            raise IdentityRejected("identity provider failure") from exc
        if not isinstance(claims, dict):
            raise IdentityRejected("invalid claims")
        if claims.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
            raise IdentityRejected("invalid issuer")
        if claims.get("aud") != self.audience:
            raise IdentityRejected("invalid audience")
        if claims.get("email_verified") is not True:
            raise IdentityRejected("unverified email")
        email = claims.get("email")
        if not isinstance(email, str) or not email:
            raise IdentityRejected("missing email")
        email = email.lower()
        if required_scope == "dispatch":
            if email != self.dispatcher_email:
                raise IdentityRejected("unauthorized dispatcher")
            return Actor(email, None, frozenset({"dispatch"}), "dispatcher")
        if required_scope == "execute":
            if email != self.task_email:
                raise IdentityRejected("unauthorized worker")
            return Actor(email, None, frozenset({"execute"}), "worker")
        record = self.callers.get(email)
        if not isinstance(record, dict):
            raise IdentityRejected("caller not allowlisted")
        tenant = record.get("tenant")
        scopes = record.get("scopes")
        if (not isinstance(tenant,str) or not tenant or not isinstance(scopes,list)
                or not all(isinstance(x,str) for x in scopes)
                or required_scope not in scopes):
            raise IdentityRejected("caller missing scope or tenant")
        return Actor(email, tenant, frozenset(scopes), "caller")
