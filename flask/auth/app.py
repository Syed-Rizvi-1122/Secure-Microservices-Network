"""
Auth Microservice — JWT Token Issuing and Verification
=======================================================
Endpoints:
  POST /auth/token   — Issue a JWT for valid credentials
  GET  /auth/verify  — Verify a Bearer token
  GET  /health       — Health check
  GET  /metrics      — Prometheus metrics
"""

from flask import Flask, request, jsonify
import jwt
import time
import os
import ssl
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "nps-project-secret-2026")
TOKEN_TTL = int(os.getenv("TOKEN_TTL_SECONDS", "3600"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "auth")

# ── Hardcoded credential store (no database required) ────────────────────────
CREDENTIALS = {
    "alice": "password123",
    "bob": "securepass",
    "admin": "adminpass",
}

# ── Prometheus metrics ───────────────────────────────────────────────────────
AUTH_REQUEST_COUNT = Counter(
    'auth_requests_total',
    'Total authentication requests',
    ['endpoint', 'status']
)


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.route("/auth/token", methods=["POST"])
def issue_token():
    """Issue a JWT token for valid credentials."""
    data = request.get_json(silent=True)

    if not data or "username" not in data or "password" not in data:
        AUTH_REQUEST_COUNT.labels(endpoint="/auth/token", status="400").inc()
        return jsonify({"error": "Missing username or password"}), 400

    username = data["username"]
    password = data["password"]

    # Validate credentials
    if username not in CREDENTIALS or CREDENTIALS[username] != password:
        AUTH_REQUEST_COUNT.labels(endpoint="/auth/token", status="401").inc()
        return jsonify({"error": "Invalid credentials"}), 401

    # Issue JWT
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + TOKEN_TTL,
        "key": "nps-jwt-key",
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    AUTH_REQUEST_COUNT.labels(endpoint="/auth/token", status="200").inc()
    return jsonify({"token": token, "expires_in": TOKEN_TTL}), 200


@app.route("/auth/verify", methods=["GET"])
def verify_token():
    """Verify a Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        AUTH_REQUEST_COUNT.labels(endpoint="/auth/verify", status="401").inc()
        return jsonify({"error": "Missing or malformed Authorization header"}), 401

    token = auth_header[7:]  # Strip "Bearer "

    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        AUTH_REQUEST_COUNT.labels(endpoint="/auth/verify", status="200").inc()
        return jsonify({"valid": True, "sub": decoded["sub"]}), 200
    except jwt.ExpiredSignatureError:
        AUTH_REQUEST_COUNT.labels(endpoint="/auth/verify", status="401").inc()
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        AUTH_REQUEST_COUNT.labels(endpoint="/auth/verify", status="401").inc()
        return jsonify({"error": "Invalid token"}), 401


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "auth"}), 200


@app.route("/metrics", methods=["GET"])
def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Check if certs exist for mTLS
    cert_file = f"/certs/{SERVICE_NAME}.crt"
    key_file = f"/certs/{SERVICE_NAME}.key"
    ca_file = "/certs/ca.crt"

    if os.path.exists(cert_file) and os.path.exists(key_file) and os.path.exists(ca_file):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_file, key_file)
        ctx.load_verify_locations(ca_file)
        ctx.verify_mode = ssl.CERT_REQUIRED
        print(f"[{SERVICE_NAME}] Starting with mTLS enabled (CERT_REQUIRED)")
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, ssl_context=ctx)
    else:
        print(f"[{SERVICE_NAME}] WARNING: Certs not found, starting without TLS")
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
