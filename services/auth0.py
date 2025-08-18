import os, time, json, base64, hashlib
import secrets
import requests
from urllib.parse import urlencode
from jose import jwt
from jose.utils import base64url_decode
from config import settings

AUTH0_DOMAIN = settings.auth0_domain
CLIENT_ID = settings.auth0_client_id
CLIENT_SECRET = settings.auth0_client_secret
REDIRECT_URI = settings.auth0_redirect_uri
AUDIENCE = settings.auth0_audience or None
SCOPES = "openid profile email"

def _auth0_base(path: str) -> str:
    if not AUTH0_DOMAIN:
        raise RuntimeError("AUTH0_DOMAIN not configured")
    return f"https://{AUTH0_DOMAIN}{path}"

def build_login_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    }
    if AUDIENCE:
        params["audience"] = AUDIENCE
    return _auth0_base("/authorize") + "?" + urlencode(params)

def build_logout_url() -> str:
    params = {
        "client_id": CLIENT_ID,
        "returnTo": REDIRECT_URI,
    }
    return _auth0_base("/v2/logout") + "?" + urlencode(params)

def exchange_code_for_tokens(code: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    resp = requests.post(_auth0_base("/oauth/token"), data=data, timeout=15)
    resp.raise_for_status()
    return resp.json()  # contains access_token, id_token, token_type, expires_in

# ---- ID token validation (Auth0 RS256)
_JWKS_CACHE = None
_JWKS_TS = 0

def _get_jwks() -> dict:
    global _JWKS_CACHE, _JWKS_TS
    if _JWKS_CACHE and time.time() - _JWKS_TS < 3600:
        return _JWKS_CACHE
    jwks = requests.get(_auth0_base("/.well-known/jwks.json"), timeout=10).json()
    _JWKS_CACHE = jwks
    _JWKS_TS = time.time()
    return jwks

def verify_id_token(id_token: str) -> dict:
    jwks = _get_jwks()
    unverified_header = jwt.get_unverified_header(id_token)
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header.get("kid"):
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
            break
    if not rsa_key:
        raise ValueError("Appropriate JWK not found")

    payload = jwt.decode(
        id_token,
        rsa_key,
        algorithms=["RS256"],
        audience=CLIENT_ID,
        issuer=f"https://{AUTH0_DOMAIN}/"
    )
    return payload  # dict with sub, email, name, etc.

def new_state() -> str:
    return secrets.token_urlsafe(24)
