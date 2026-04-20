# Distributed Systems Networking -- API Gateway + Microservices + Monitoring

This project demonstrates a **microservices architecture** with **Flask**, **PostgreSQL**, **Docker Compose**, **Apache APISIX** as the API Gateway, and **Prometheus + Grafana** for monitoring and observability.

## 🚀 **Quick Start (3 Commands)**

```bash
docker compose down --volumes && docker compose build --no-cache && docker compose up -d
```

Wait ~30 seconds for all services to be ready.

------------------------------------------------------------------------

## 🐳 **Troubleshooting: Docker Credential Issues**

If you see errors like `docker-credential-desktop.exe: exec format error`:

```bash
cat ~/.docker/config.json
cp ~/.docker/config.json ~/.docker/config.json.bak
echo '{}' > ~/.docker/config.json
docker compose build --no-cache
```

------------------------------------------------------------------------

## 📊 **View Live Metrics (After Starting)**

Once containers are running, access the dashboards:

### **1. Grafana** (Service-level metrics with histograms & latency)
```
URL: http://localhost:3000
Login: admin / admin
Navigate: Dashboards → Flask Services Monitoring
```

### **2. Prometheus** (Raw metrics query interface)
```
URL: http://localhost:9090
Example query: flask_http_requests_total
```

### **3. APISIX Dashboard** (API Gateway admin)
```
URL: http://localhost:9000
Login: admin / admin
```

------------------------------------------------------------------------

## 🔧 **APISIX Setup & Routing Configuration**

After `docker compose up -d` succeeds, configure APISIX upstreams and routes for all service endpoints and health checks.

### **Working Gateway Endpoints**

**Service API:**
- `POST /users` → users service
- `POST /products` → products service
- `POST /orders` → orders service
- `GET /users`, `GET /products`, `GET /orders` (if implemented)

**Health Checks:**
- `GET /users/health` → users service `/health`
- `GET /products/health` → products service `/health`
- `GET /orders/health` → orders service `/health`

**Wildcard Routes (Path Rewriting):**
- `/users/*` → `/` on users backend (e.g., `/users/health` → `/health`)
- `/products/*` → `/` on products backend
- `/orders/*` → `/` on orders backend

**Rate Limiting & Retries:**
- All routes have rate limiting (100 req/60s per IP) and retries (2 attempts, 2s timeout)

### **How APISIX Is Configured**

Upstreams:
```bash
curl -X PUT "http://localhost:9180/apisix/admin/upstreams/users_upstream" \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" \
  -H "Content-Type: application/json" \
  -d '{"type": "roundrobin", "nodes": {"users:5000": 1}, "retries": 2, "retry_timeout": 2}'
curl -X PUT "http://localhost:9180/apisix/admin/upstreams/products_upstream" \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" \
  -H "Content-Type: application/json" \
  -d '{"type": "roundrobin", "nodes": {"products:5000": 1}, "retries": 2, "retry_timeout": 2}'
curl -X PUT "http://localhost:9180/apisix/admin/upstreams/orders_upstream" \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" \
  -H "Content-Type: application/json" \
  -d '{"type": "roundrobin", "nodes": {"orders:5000": 1}, "retries": 2, "retry_timeout": 2}'
```

Root routes:
```bash
curl -X PUT "http://localhost:9180/apisix/admin/routes/users_root" \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" \
  -H "Content-Type: application/json" \
  -d '{"name": "users_root", "uri": "/users", "methods": ["POST","GET"], "upstream_id": "users_upstream", "plugins": {"limit-count": {"count": 100, "time_window": 60, "rejected_code": 429, "key": "remote_addr", "policy": "local"}}}'
curl -X PUT "http://localhost:9180/apisix/admin/routes/products_root" \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" \
  -H "Content-Type: application/json" \
  -d '{"name": "products_root", "uri": "/products", "methods": ["POST","GET"], "upstream_id": "products_upstream", "plugins": {"limit-count": {"count": 100, "time_window": 60, "rejected_code": 429, "key": "remote_addr", "policy": "local"}}}'
curl -X PUT "http://localhost:9180/apisix/admin/routes/orders_root" \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" \
  -H "Content-Type: application/json" \
  -d '{"name": "orders_root", "uri": "/orders", "methods": ["POST","GET"], "upstream_id": "orders_upstream", "plugins": {"limit-count": {"count": 100, "time_window": 60, "rejected_code": 429, "key": "remote_addr", "policy": "local"}}}'
```

Wildcard routes with path rewriting:
```bash
curl -X PUT "http://localhost:9180/apisix/admin/routes/users_wildcard" \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" \
  -H "Content-Type: application/json" \
  -d '{"name": "users_wildcard", "uri": "/users/*", "upstream_id": "users_upstream", "plugins": {"proxy-rewrite": {"regex_uri": ["^/users/(.*)", "/$1"]}, "limit-count": {"count": 100, "time_window": 60, "rejected_code": 429, "key": "remote_addr", "policy": "local"}}}'
curl -X PUT "http://localhost:9180/apisix/admin/routes/products_wildcard" \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" \
  -H "Content-Type: application/json" \
  -d '{"name": "products_wildcard", "uri": "/products/*", "upstream_id": "products_upstream", "plugins": {"proxy-rewrite": {"regex_uri": ["^/products/(.*)", "/$1"]}, "limit-count": {"count": 100, "time_window": 60, "rejected_code": 429, "key": "remote_addr", "policy": "local"}}}'
curl -X PUT "http://localhost:9180/apisix/admin/routes/orders_wildcard" \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" \
  -H "Content-Type: application/json" \
  -d '{"name": "orders_wildcard", "uri": "/orders/*", "upstream_id": "orders_upstream", "plugins": {"proxy-rewrite": {"regex_uri": ["^/orders/(.*)", "/$1"]}, "limit-count": {"count": 100, "time_window": 60, "rejected_code": 429, "key": "remote_addr", "policy": "local"}}}'
```

**Test health endpoints:**
```bash
curl -s http://localhost:9080/users/health
curl -s http://localhost:9080/products/health
curl -s http://localhost:9080/orders/health
# All should return OK
```

**Test API endpoints:**
```bash
curl -X POST http://localhost:9080/users -H 'Content-Type: application/json' -d '{"name":"UserTest","email":"usertest@test.com"}'
curl -X POST http://localhost:9080/products -H 'Content-Type: application/json' -d '{"name":"ProductTest","price":123}'
curl -X POST http://localhost:9080/orders -H 'Content-Type: application/json' -d '{"user_id":1,"product_id":1,"quantity":2}'
```

**Rate limiting and retries are active on all routes.**

------------------------------------------------------------------------

## 🧪 **Generate Traffic & View Metrics (Step-by-Step)**

### **Step 1: Send Sample Requests**

```bash
# Create 5 users
for i in {1..5}; do
  curl -X POST http://localhost:9080/users \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"User$i\",\"email\":\"user$i@test.com\"}"
done

# Create 3 products
for i in {1..3}; do
  curl -X POST http://localhost:9080/products \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"Product$i\",\"price\":$((i * 100))}"
done

# Create 2 orders
for i in {1..2}; do
  curl -X POST http://localhost:9080/orders \
    -H 'Content-Type: application/json' \
    -d "{\"user_id\":1,\"product_id\":$i,\"quantity\":$i}"
done
```

### **Step 2: Verify Metrics Collection**

Check that Prometheus is scraping the services:

```bash
curl -s 'http://localhost:9090/api/v1/targets' | jq '.data.activeTargets[] | {job: .labels.job, state: .health}'
```

Expected output:
```json
{ "job": "apisix", "state": "up" }
{ "job": "users", "state": "up" }
{ "job": "products", "state": "up" }
{ "job": "orders", "state": "up" }
```

### **Step 3: View Dashboard**

1. Open **Grafana**: http://localhost:3000
2. Login with `admin` / `admin`
3. Click **Dashboards** (left sidebar)
4. Select **Flask Services Monitoring**
5. You should see:
   - **Service Requests Per Second** — line chart with traffic
   - **Service Request Latency (p95, p99)** — latency percentiles
   - **HTTP Status Codes by Service** — 2xx/4xx/5xx distribution
   - **Total Requests by Service** — pie chart

------------------------------------------------------------------------

## 📊 **Monitoring Architecture**

### **Service Instrumentation**

Each Flask service (`users`, `products`, `orders`) exports Prometheus metrics:

- **`flask_http_requests_total`** — Counter of HTTP requests by service, method, endpoint, and HTTP status
- **`flask_request_latency_seconds`** — Histogram of request latency (enables p95/p99 calculations)
- **Metrics endpoint**: `http://<service>:5000/metrics`

### **Prometheus Configuration**

Configured to scrape:
- `apisix:9091/apisix/prometheus/metrics` — APISIX gateway metrics
- `users:5000/metrics` — Users service metrics
- `products:5000/metrics` — Products service metrics
- `orders:5000/metrics` — Orders service metrics

### **Accessing Prometheus & Query Examples**

#### **Step 1: Open Prometheus**
1. Open your browser and go to: `http://localhost:9090`
2. You should see the Prometheus query interface with a search bar

#### **Step 2: Run Queries in Prometheus**

Copy and paste these queries into the search bar and press Enter:

**Query 1: Requests Per Second by Service**
```promql
sum(rate(flask_http_requests_total[1m])) by (service)
```
This shows how many requests per second each service is handling.

**Query 2: Request Latency (p95 percentile)**
```promql
histogram_quantile(0.95, sum(rate(flask_request_latency_seconds_bucket[5m])) by (le, service))
```
Shows 95th percentile response time for each service (0.95 = 95%).

**Query 3: Request Latency (p99 percentile)**
```promql
histogram_quantile(0.99, sum(rate(flask_request_latency_seconds_bucket[5m])) by (le, service))
```
Shows 99th percentile response time (slowest 1% of requests).

**Query 4: Error Rate (4xx + 5xx) Per Service**
```promql
sum(rate(flask_http_requests_total{http_status=~"(4|5).."}[1m])) by (service)
```
Shows errors per second for each service.

**Query 5: Total Requests by Endpoint**
```promql
sum(increase(flask_http_requests_total[5m])) by (endpoint, service)
```
Shows total request count per endpoint in the last 5 minutes.

**Query 6: Active APISIX Connections**
```promql
apisix_nginx_http_current_connections{state="active"}
```
Shows currently active connections on the APISIX gateway.

#### **Step 3: View Query Results**
- Results appear in two tabs: **Table** (numerical data) and **Graph** (time-series visualization)
- Click the **Graph** tab to see a line chart over time
- Hover over the graph to see exact values at specific times

### **Grafana Dashboards**

#### **Step 1: Open Grafana**
1. Open your browser and go to: `http://localhost:3000`
2. You'll see the Grafana login page
3. Login with:
   - **Username**: `admin`
   - **Password**: `admin`

#### **Step 2: Navigate to Dashboards**
1. Click the **Dashboards** icon (grid icon) in the left sidebar
2. Click **Browse** or **View all dashboards**
3. You should see two pre-provisioned dashboards:
   - **APISIX Gateway Monitoring**
   - **Flask Services Monitoring**

#### **Step 3: View Flask Services Monitoring Dashboard**
1. Click on **Flask Services Monitoring**
2. You will see four panels:
   - **Service Requests Per Second** — Line chart showing RPS trends for each service
   - **Service Request Latency (p95, p99)** — Shows 95th and 99th percentile latencies
   - **HTTP Status Codes by Service** — Stacked bar chart showing 2xx/4xx/5xx breakdown
   - **Total Requests by Service** — Pie chart showing request volume distribution

#### **Step 4: View APISIX Gateway Monitoring Dashboard**
1. Go back to Dashboards and click on **APISIX Gateway Monitoring**
2. This dashboard shows:
   - **Active Connections** — Current active connections to APISIX
   - **etcd Health** — Status of the configuration store
   - **Plugin Status** — Enabled plugins on routes
   - **HTTP Requests Total** — Overall request volume

#### **Step 5: Customize Dashboards (Optional)**
1. Click the **Edit** button (pencil icon) in the top right
2. Click on any panel to modify its query or settings
3. Click **Save** to persist changes

#### **Generate Live Traffic to See Metrics**

Run this command to generate continuous traffic:
```bash
# Generate 15 minutes of random traffic
for i in {1..180}; do
  sleep $((RANDOM % 5 + 2))  # Random 2-7 second delay
  curl -X POST http://localhost:9080/users -H 'Content-Type: application/json' -d "{\"name\":\"User$((RANDOM % 1000))\",\"email\":\"user$((RANDOM % 1000))@test.com\"}" > /dev/null 2>&1 &
  curl -X POST http://localhost:9080/products -H 'Content-Type: application/json' -d "{\"name\":\"Product$((RANDOM % 100))\",\"price\":$((RANDOM % 500 + 10))}" > /dev/null 2>&1 &
  curl -X POST http://localhost:9080/orders -H 'Content-Type: application/json' -d "{\"user_id\":$((RANDOM % 10 + 1)),\"product_id\":$((RANDOM % 5 + 1)),\"quantity\":$((RANDOM % 5 + 1))}" > /dev/null 2>&1 &
done
```

Then:
1. Switch to Grafana and watch the **Flask Services Monitoring** dashboard update in real-time
2. Switch to Prometheus and run queries to see live metrics
3. Return to Grafana to see latency percentiles and error rates populate

------------------------------------------------------------------------

## 🗄️ **Database & Data Verification**

### **Access PostgreSQL**

```bash
docker exec -it distributed-systems-networking-db-1 psql -U postgres -d ecommerce
```

### **Check Tables**

```sql
SELECT * FROM users;
SELECT * FROM products;
SELECT * FROM orders;
```

### **Exit PostgreSQL**

```
\q
```

------------------------------------------------------------------------

## 📂 **Project Structure**

```
.
├── docker-compose.yml              # Service orchestration (APISIX, services, DB, Prometheus, Grafana)
├── flask/
│   ├── users/
│   │   ├── app.py                 # Users microservice with Prometheus instrumentation
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── products/
│   │   ├── app.py                 # Products microservice with Prometheus instrumentation
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── orders/
│       ├── app.py                 # Orders microservice with Prometheus instrumentation
│       ├── Dockerfile
│       └── requirements.txt
├── db/
│   └── init.sql                   # PostgreSQL schema (auto-initialized)
├── apisix_conf/
│   └── config.yaml                # APISIX configuration with Prometheus plugin enabled
├── dashboard_conf/
│   └── conf.yaml                  # APISIX Dashboard configuration
├── prometheus/
│   └── prometheus.yml             # Prometheus scrape config (APISIX + services)
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── prometheus.yml     # Auto-provision Prometheus as Grafana data source
        └── dashboards/
            ├── apisix-dashboard.json        # APISIX gateway monitoring dashboard
            └── services-monitoring.json     # Flask services monitoring dashboard
```

------------------------------------------------------------------------

## 💾 **Persistent Storage**

Metrics and configuration data are persisted in Docker volumes:

- **`prometheus_data`** — Prometheus time-series database
- **`grafana_data`** — Grafana dashboards and configuration
- **`etcd_data`** — APISIX configuration store

Data survives container restarts.

------------------------------------------------------------------------

## 🎯 **Available Endpoints**

### **API Gateway (APISIX)**

- **Admin API**: `http://localhost:9180/` (API key required)
- **Dashboard**: `http://localhost:9000/` (admin:admin)
- **Gateway**: `http://localhost:9080/` (public)
  - POST `/users` → users service
  - POST `/products` → products service
  - POST `/orders` → orders service

### **Microservices** (direct, bypassing gateway)

- **Users**: `http://localhost:5001/` (with `/metrics`)
- **Products**: `http://localhost:5002/` (with `/metrics`)
- **Orders**: `http://localhost:5003/` (with `/metrics`)

### **Database**

- **PostgreSQL**: `localhost:5432` (postgres:password)

### **Monitoring**

- **Prometheus**: `http://localhost:9090/`
- **Grafana**: `http://localhost:3000/` (admin:admin)

------------------------------------------------------------------------

## 🔍 **Common PromQL Queries**

Use these in Prometheus (http://localhost:9090) or Grafana to create custom visualizations:

```promql
# Requests per second by service
sum(rate(flask_http_requests_total[1m])) by (service)

# Error rate (4xx + 5xx) per service
sum(rate(flask_http_requests_total{http_status=~"(4|5).."}[1m])) by (service)

# P95 request latency
histogram_quantile(0.95, sum(rate(flask_request_latency_seconds_bucket[5m])) by (le, service))

# P99 request latency
histogram_quantile(0.99, sum(rate(flask_request_latency_seconds_bucket[5m])) by (le, service))

# Request count by endpoint
sum(increase(flask_http_requests_total[5m])) by (endpoint, service)

# Active APISIX connections
apisix_nginx_http_current_connections{state="active"}

# Total requests (all services)
sum(increase(flask_http_requests_total[5m]))
```

------------------------------------------------------------------------

## 🚀 **Production Checklist**

- [ ] Change APISIX API key from default (`edd1c9f034335f136f87ad84b625c8f1`)
- [ ] Change Grafana admin password from default (`admin`)
- [ ] Change PostgreSQL password from default (`password`)
- [ ] Configure persistent volumes for production storage
- [ ] Set up log aggregation (ELK, Loki, Splunk, etc.)
- [ ] Enable HTTPS/TLS for all services
- [ ] Configure alerting rules in Prometheus/Grafana
- [ ] Set resource limits in `docker-compose.yml`
- [ ] Enable rate limiting across all routes
- [ ] Monitor and set up backups for PostgreSQL

------------------------------------------------------------------------

## 📚 **Technology Stack**

| Component | Purpose | Technology |
|-----------|---------|-----------|
| API Gateway | Request routing, rate limiting, Prometheus export | Apache APISIX 3.14+ |
| Microservices | Business logic | Flask 2.3 + SQLAlchemy |
| Database | Persistent data | PostgreSQL 15 |
| Metrics Collection | Time-series metrics | Prometheus |
| Metrics Visualization | Live dashboards | Grafana |
| Instrumentation | Service metrics | prometheus_client 0.16 |
| Configuration | Service discovery | etcd 3.4 |
| Orchestration | Container management | Docker Compose |

------------------------------------------------------------------------

## 🎯 **Project Summary**

You now have:

- **3 Flask microservices** (users, products, orders) with **Prometheus instrumentation**
- **1 PostgreSQL database** with auto-created tables
- **Apache APISIX** API Gateway with rate limiting and Prometheus metrics
- **Prometheus** collecting metrics from APISIX + all three services
- **Grafana** with **two pre-built dashboards** for monitoring
- **Full observability** with request rates, latencies (p95/p99), error rates, and status codes
- **Docker Compose** orchestrating everything

Everything is aligned for a complete **distributed systems + networking university project** with **production-ready monitoring & observability**.

------------------------------------------------------------------------

Made with ❤️ by **Shazan**, **Zain**, **Abdul Wasay**
