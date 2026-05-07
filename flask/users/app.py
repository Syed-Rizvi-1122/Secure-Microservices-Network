from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import sys
import ssl
import time
from flask import g
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

SERVICE_NAME = os.getenv("SERVICE_NAME", "users")

class User(db.Model):
    __tablename__ = "users"   # 👈 IMPORTANT: match init.sql
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)

@app.route("/users", methods=["POST"])
def add_user():
    data = request.json
    new_user = User(name=data["name"], email=data["email"])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User added", "user_id": new_user.id}), 201


@app.route("/users", methods=["GET"])
def list_users():
    users = User.query.all()
    return jsonify([{"id": u.id, "name": u.name, "email": u.email} for u in users]), 200


# Prometheus metrics — includes 'subject' label for non-repudiation (FR-024)
REQUEST_COUNT = Counter(
    'flask_http_requests_total',
    'Total HTTP requests',
    ['service', 'method', 'endpoint', 'http_status', 'subject']
)
REQUEST_LATENCY = Histogram(
    'flask_request_latency_seconds',
    'Request latency in seconds',
    ['service', 'endpoint']
)


@app.before_request
def start_timer():
    g.start_time = time.time()


@app.after_request
def record_metrics(response):
    try:
        latency = time.time() - g.start_time
    except Exception:
        latency = 0
    # Read subject from X-Authenticated-User header (injected by APISIX after JWT validation)
    subject = request.headers.get('X-Authenticated-User', 'anonymous')
    REQUEST_LATENCY.labels(service=SERVICE_NAME, endpoint=request.path).observe(latency)
    REQUEST_COUNT.labels(
        service=SERVICE_NAME,
        method=request.method,
        endpoint=request.path,
        http_status=response.status_code,
        subject=subject
    ).inc()
    return response


@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200


# ── Register IDS middleware ──────────────────────────────────────────────────
try:
    sys.path.insert(0, '/ids')
    from ids_middleware import register_ids
    register_ids(app)
    print(f"[{SERVICE_NAME}] IDS middleware registered successfully")
except Exception as e:
    print(f"[{SERVICE_NAME}] WARNING: Could not load IDS middleware: {e}")


if __name__ == "__main__":
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
