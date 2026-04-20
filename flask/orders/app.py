from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import time
from flask import g
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Order(db.Model):
    __tablename__ = "orders"   # 👈 IMPORTANT
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    product_id = db.Column(db.Integer)
    quantity = db.Column(db.Integer)

@app.route("/orders", methods=["POST"])
def add_order():
    data = request.json
    new_order = Order(
        user_id=data["user_id"],
        product_id=data["product_id"],
        quantity=data["quantity"],
    )
    db.session.add(new_order)
    db.session.commit()
    return jsonify({"message": "Order placed", "order_id": new_order.id}), 201


# Prometheus metrics
REQUEST_COUNT = Counter(
    'flask_http_requests_total',
    'Total HTTP requests',
    ['service', 'method', 'endpoint', 'http_status']
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
    REQUEST_LATENCY.labels(service='orders', endpoint=request.path).observe(latency)
    REQUEST_COUNT.labels(service='orders', method=request.method, endpoint=request.path, http_status=response.status_code).inc()
    return response


@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    
@app.route('/health')
def health():
    return 'OK', 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
