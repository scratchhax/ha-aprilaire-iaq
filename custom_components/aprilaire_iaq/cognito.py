"""AWS Cognito SRP-6a client for AprilAire, standard library only.

AprilAire's user pool is us-west-2_skfkpmVv6 with a public app client (no client
secret), so the auth dance is USER_SRP_AUTH -> PASSWORD_VERIFIER. Group constants
come from amazon-cognito-identity-js.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request

POOL_ID = "us-west-2_skfkpmVv6"
CLIENT_ID = "3aiakr6qdoqtajv7qgtapecerg"
REGION = "us-west-2"
ENDPOINT = f"https://cognito-idp.{REGION}.amazonaws.com/"
POOL_NAME = POOL_ID.split("_")[1]

N_HEX = "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF"
G_HEX = "2"
INFO_BITS = b"Caldera Derived Key"

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _sha_hex(buf: bytes) -> str:
    return "%064x" % int(hashlib.sha256(buf).hexdigest(), 16)


def _hex_hash(hex_string: str) -> str:
    return _sha_hex(bytearray.fromhex(hex_string))


def _pad(value) -> str:
    """Pad to even-length hex, keeping the value positive when hashed as bytes."""
    out = f"{value:x}" if not isinstance(value, str) else value
    if len(out) % 2 == 1:
        out = "0" + out
    elif out[0] in "89ABCDEFabcdef":
        out = "00" + out
    return out


def _post(target: str, payload: dict) -> dict:
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": f"AWSCognitoIdentityProviderService.{target}",
            "User-Agent": "Mozilla/5.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HTTP {err.code} on {target}: {detail}") from None


def _timestamp() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return (
        f"{_DAYS[now.weekday()]} {_MONTHS[now.month - 1]} {now.day:02d} "
        f"{now:%H:%M:%S} UTC {now.year}"
    )


def authenticate(username: str, password: str) -> dict:
    """Run SRP-6a and return IdToken / AccessToken / RefreshToken."""
    modulus = int(N_HEX, 16)
    generator = int(G_HEX, 16)
    k = int(_hex_hash("00" + N_HEX + "0" + G_HEX), 16)
    small_a = int.from_bytes(os.urandom(128), "big") % modulus
    large_a = pow(generator, small_a, modulus)

    init = _post(
        "InitiateAuth",
        {
            "AuthFlow": "USER_SRP_AUTH",
            "ClientId": CLIENT_ID,
            "AuthParameters": {"USERNAME": username, "SRP_A": "%X" % large_a},
        },
    )
    params = init.get("ChallengeParameters") or {}
    if not params:
        raise RuntimeError(f"unexpected auth response: {list(init)}")

    user_id = params["USER_ID_FOR_SRP"]
    salt = params["SALT"]
    large_b = int(params["SRP_B"], 16)
    secret_block = base64.standard_b64decode(params["SECRET_BLOCK"])

    u = int(_hex_hash(_pad(large_a) + _pad(large_b)), 16)
    if u == 0:
        raise RuntimeError("U cannot be zero")
    x = int(
        _hex_hash(
            _pad(salt)
            + _sha_hex(f"{POOL_NAME}{user_id}:{password}".encode())
        ),
        16,
    )
    shared = pow((large_b - k * pow(generator, x, modulus)) % modulus, small_a + u * x, modulus)

    prk = hmac.new(
        bytearray.fromhex(_pad(u)), bytearray.fromhex(_pad(shared)), hashlib.sha256
    ).digest()
    hkdf = hmac.new(prk, INFO_BITS + b"\x01", hashlib.sha256).digest()[:16]

    stamp = _timestamp()
    message = POOL_NAME.encode() + user_id.encode() + secret_block + stamp.encode()
    signature = base64.standard_b64encode(hmac.new(hkdf, message, hashlib.sha256).digest())

    result = _post(
        "RespondToAuthChallenge",
        {
            "ClientId": CLIENT_ID,
            "ChallengeName": "PASSWORD_VERIFIER",
            "Session": init.get("Session"),
            "ChallengeResponses": {
                "USERNAME": username,
                "TIMESTAMP": stamp,
                "PASSWORD_CLAIM_SECRET_BLOCK": params["SECRET_BLOCK"],
                "PASSWORD_CLAIM_SIGNATURE": signature.decode(),
            },
        },
    ).get("AuthenticationResult") or {}
    if not result.get("IdToken"):
        raise RuntimeError(f"auth failed: {result or 'no authentication result'}")
    return result


def refresh(refresh_token: str) -> dict:
    """Swap a refresh token for fresh id/access tokens."""
    result = _post(
        "InitiateAuth",
        {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": CLIENT_ID,
            "AuthParameters": {"REFRESH_TOKEN": refresh_token},
        },
    ).get("AuthenticationResult") or {}
    if not result.get("IdToken"):
        raise RuntimeError("refresh failed")
    result.setdefault("RefreshToken", refresh_token)
    result.setdefault("ExpiresIn", 3600)
    return result
