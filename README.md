# Secure Microservices Network

**CS4068 — Network Protocols and Standards, Spring 2026**
**FAST-NUCES Karachi**

A containerised e-commerce microservices platform with a comprehensive network security layer: **mTLS encryption**, **JWT authentication**, **IDS/IPS**, **attack simulation**, and **live observability**.

---

## 📋 Table of Contents

1. [Architecture Overview](#-architecture-overview)
2. [Prerequisites](#-prerequisites)
3. [Quick Start (Full Deployment)](#-quick-start-full-deployment)
4. [Demo Walkthrough for Judge/Teacher](#-demo-walkthrough-for-judgeteacher)
   - [Module A — End-to-End Encryption (mTLS)](#module-a--end-to-end-encryption-mtls)
   - [Module B — JWT Authentication & Non-Repudiation](#module-b--jwt-authentication--non-repudiation)
   - [Module C — Attack Simulation Scripts](#module-c--attack-simulation-scripts)
   - [Module D — IDS/IPS & Firewall](#module-d--idsips--firewall)
   - [Observability — Grafana Dashboards](#observability--grafana-dashboards)
5. [Project Structure](#-project-structure)
6. [Service Inventory](#-service-inventory)
7. [Technology Stack](#-technology-stack)
8. [Course Coverage](#-course-coverage)
9. [Troubleshooting](#-troubleshooting)

---

## 🏗️ Architecture Overview

The system implements a **defence-in-depth** security model across multiple layers. Every arrow in the diagram below represents an encrypted, mutually-authenticated TLS connection — no plaintext communication exists between any two services.

```
                    ┌─────────────────────────────────────────────────────┐
                    │                   EXTERNAL CLIENTS                  │
                    │            (curl / attack scripts / browser)        │
                    └──────────────┬──────────────────┬───────────────────┘
                                   │ HTTP :9080       │ HTTPS :9443
                    ┌──────────────▼──────────────────▼──────────────────┐
                    │              APACHE APISIX (Gateway)               │
                    │   • JWT Authentication (jwt-auth plugin)           │
                    │   • Rate Limiting (100 req/60s per IP)             │
                    │   • Static Firewall (ip-restriction plugin)        │
                    │   • TLS Termination + mTLS to upstreams            │
                    │   • X-Authenticated-User header injection          │
                    └───┬──────────┬──────────┬──────────┬───────────────┘
                        │ mTLS     │ mTLS     │ mTLS     │ mTLS
                   ┌────▼───┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐
                   │ Users  │ │Products│ │ Orders │ │ Auth   │
                   │ :5000  │ │ :5000  │ │ :5000  │ │ :5000  │
                   │ (mTLS) │ │ (mTLS) │ │ (mTLS) │ │(mTLS)  │
                   │+IDS/IPS│ │+IDS/IPS│ │+IDS/IPS│ │        │
                   └───┬────┘ └───┬────┘ └───┬────┘ └────────┘
                       │          │          │
                   ┌───▼──────────▼──────────▼────┐   ┌──────────┐
                   │     PostgreSQL (ecommerce)   │   │  Redis   │
                   │           :5432              │   │  :6379   │
                   └──────────────────────────────┘   └──────────┘
                                                      (IDS counters
                    ┌────────────────────────────────┐ + blocklist)
                    │  Prometheus :9090 (mTLS scrape)│
                    │  Grafana    :3000 (8 panels)   │
                    └────────────────────────────────┘
```

### How the Security Layers Work Together

1. **Layer 1 — Transport Encryption (mTLS):** Every service runs with `ssl.CERT_REQUIRED`. Any caller that doesn't present a certificate signed by our project CA is rejected at the TLS handshake — before any HTTP code runs. This is true mutual TLS: both sides authenticate each other.

2. **Layer 2 — Identity & Access (JWT):** The API gateway validates JWT tokens on every request to protected routes. It extracts the `sub` claim (e.g., `alice`) and injects it as an `X-Authenticated-User` header. The raw token is stripped (`hide_credentials: true`) so Flask services never see it — they trust the gateway's assertion.

3. **Layer 3 — Intrusion Detection (IDS/IPS):** A Python middleware bind-mounted into each Flask service monitors every request. It uses Redis sliding-window counters to detect rate anomalies, IP spoofing (via `X-Forwarded-For` header inspection), and endpoint hammering. When thresholds are exceeded, it auto-blocks the IP via the APISIX `ip-restriction` plugin, using a Redis distributed lock to prevent race conditions.

4. **Layer 4 — Static Firewall:** Known-bad CIDR ranges (`203.0.113.0/24`, `198.51.100.0/24`, `100.64.0.0/10`) are pre-configured as blocklists on all gateway routes. The IPS dynamic sync merges with these static rules so they're never accidentally removed.

---

## ✅ Prerequisites

| Requirement | Version |
|---|---|
| **Docker Desktop** (with WSL 2 backend) | Latest |
| **WSL 2** (Ubuntu) | 22.04+ |
| **openssl** (in WSL) | Any |
| **Python 3** (in WSL, for attack scripts) | 3.8+ |

Set up the Python virtual environment and install dependencies from `requirements.txt`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 🚀 Quick Start (Full Deployment)

Run these commands **in WSL**, from the project root:

```bash
# Step 1: Generate TLS certificates (CA + 6 service certs)
bash certs/generate-certs.sh

# Step 2: Build all Docker images and start 11 containers
docker compose build --no-cache && docker compose up -d

# Step 3: Wait for all services to be ready (~45 seconds)
sleep 45

# Step 4: Configure the API Gateway (routes, JWT, firewall)
bash init-gateway.sh

# Step 5: Verify all services are running
docker compose ps
```

You should see **11 services** all in `running` state.

---

## 🎓 Demo Walkthrough for Judge/Teacher

> **This section is designed as a step-by-step demo script.** Each module starts with a conceptual explanation of *what* and *why*, followed by hands-on commands with expected outputs. Follow in order.

> **Important:** Activate the virtual environment before running attack scripts:
> ```bash
> source .venv/bin/activate
> ```

---

### Module A — End-to-End Encryption (mTLS)

#### 💡 What This Demonstrates

**Mutual TLS (mTLS)** extends standard TLS by requiring *both* sides of a connection to present certificates. In standard HTTPS, only the server proves its identity. With mTLS, the client must also prove who it is — if it can't, the connection is rejected at the TCP/TLS handshake level, before any application code executes.

This is critical in microservices because services communicate over a shared Docker network. Without mTLS, any container on that network could impersonate a legitimate service. With mTLS, every service must present a certificate signed by our project CA (`NPS-Project-CA`), ensuring that only authorised services can communicate.

**Course relevance:** Week 12 (CIA Triad — Confidentiality), Week 13 (SSL/TLS)

#### A1. Verify HTTPS works through the gateway

```bash
curl -k https://localhost:9443/users/health
```
**Expected:** `{"status":"ok"}` — The `-k` flag skips certificate verification (self-signed), but the connection IS encrypted with TLS 1.2/1.3.

#### A2. Verify HTTP still works (backward compatibility)

```bash
curl http://localhost:9080/users/health
```
**Expected:** `{"status":"ok"}` — Both HTTP and HTTPS are available at the gateway level.

#### A3. Prove mTLS is enforced at the Flask service level

This is the key test — it proves that Flask services reject connections without a valid client certificate:

```bash
curl -k https://localhost:5001/users
```
**Expected:** Connection **fails with a TLS handshake error** (curl exit code 56), NOT an HTTP error code. This proves the Flask server's `ssl.CERT_REQUIRED` setting works — the connection is killed at the socket level before any Python code runs. Only callers with a certificate signed by our CA (like APISIX or Prometheus) can connect.

#### A4. Show the certificate chain

```bash
# Verify CA identity
openssl x509 -in certs/ca.crt -noout -subject
# Expected: subject=CN = NPS-Project-CA

# Verify a service cert is signed by our CA
openssl verify -CAfile certs/ca.crt certs/users.crt
# Expected: certs/users.crt: OK

# List all certificates
ls certs/*.crt
# Expected: apisix.crt, auth.crt, ca.crt, orders.crt, products.crt, prometheus.crt, users.crt
```

---

### Module B — JWT Authentication & Non-Repudiation

#### 💡 What This Demonstrates

**JWT (JSON Web Tokens)** provide stateless authentication. When a user logs in via `POST /auth/token`, the Auth service creates a digitally signed token containing the user's identity (`sub` claim). This token is sent with every subsequent request.

The API gateway validates the token's signature using the shared secret (`nps-project-secret-2026`), extracts the `sub` claim, and injects it as an `X-Authenticated-User` header. The raw token is then **stripped** before the request reaches Flask — this is a security best practice called "credential hiding".

**Non-repudiation** means a user cannot deny having performed an action. Because every request is tagged with the authenticated user's identity in Prometheus metrics, we have a cryptographically-linked audit trail. The `subject` label on `flask_http_requests_total` proves exactly *who* made *what* request and *when*.

**Course relevance:** Week 12 (Authentication, Non-Repudiation)

#### B1. Obtain a JWT token

```bash
curl -s -X POST http://localhost:9080/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"password123"}'
```
**Expected:** `{"token":"eyJ...","expires_in":3600}` — A 3600-second (1 hour) JWT token.

#### B2. Verify unauthenticated requests are rejected

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:9080/users
```
**Expected:** `401` — The gateway's `jwt-auth` plugin rejects requests without a valid token.

#### B3. Create data through the gateway

```bash
# Store token in a variable
TOKEN=$(curl -s -X POST http://localhost:9080/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"password123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Create a user
curl -s -X POST http://localhost:9080/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice","email":"alice@example.com"}'

# Create a product
curl -s -X POST http://localhost:9080/products \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Laptop","price":999.99}'

# Place an order
curl -s -X POST http://localhost:9080/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"product_id":1,"quantity":2}'
```
**Expected:** HTTP 201 with creation success messages.

#### B4. Access protected endpoints with a valid token

```bash
# Use token to read the newly created data
curl -s http://localhost:9080/users -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:9080/products -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:9080/orders -H "Authorization: Bearer $TOKEN"
```
**Expected:** HTTP 200 with populated JSON data from each service.

#### B5. Verify non-repudiation (subject label in Prometheus)

This is the proof of non-repudiation — every request is permanently linked to the authenticated user:

```bash
# Make requests as alice and bob
for i in {1..30}; do
  curl -s http://localhost:9080/users -H "Authorization: Bearer $TOKEN" > /dev/null
done

BOB_TOKEN=$(curl -s -X POST http://localhost:9080/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"bob","password":"securepass"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

for i in {1..30}; do
  curl -s http://localhost:9080/products -H "Authorization: Bearer $BOB_TOKEN" > /dev/null
done

# Wait for Prometheus to scrape, then query
sleep 10
curl -s -G --data-urlencode 'query=flask_http_requests_total{subject=~"alice|bob"}' http://localhost:9090/api/v1/query | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data.get('data',{}).get('result',[]):
    m = r['metric']
    print(f\"  service={m.get('service','?'):10s} subject={m.get('subject','?'):10s} count={r['value'][1]}\")
"
```
**Expected:** Non-zero counts for both `alice` and `bob` — proving every request is traceable to its authenticated user.

#### B6. Verify token via /auth/verify endpoint

```bash
curl -s http://localhost:9080/auth/verify -H "Authorization: Bearer $TOKEN"
```
**Expected:** `{"sub":"alice","valid":true}` — Confirms the token is valid and belongs to alice.

#### B7. Test invalid credentials

```bash
curl -s -X POST http://localhost:9080/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"wrongpassword"}'
```
**Expected:** HTTP 401 — `{"error":"Invalid credentials"}`

---

### Module C — Attack Simulation Scripts

#### 💡 What This Demonstrates

These scripts simulate real-world network attacks from the WSL host (outside Docker), targeting the gateway. They demonstrate the attack vectors discussed in Week 13:

- **SYN Flood** (transport layer): Sends raw TCP SYN packets with forged source IPs. These packets never complete the three-way handshake, consuming server resources. Requires raw sockets (`sudo`).
- **IP Spoofing** (network layer): Injects forged IP addresses via HTTP headers (`X-Forwarded-For`, `X-Real-IP`). The IDS middleware detects these forged private/test-range IPs.
- **Brute Force** (application layer): Systematically tries username/password combinations against the auth endpoint, simulating a credential-stuffing attack.

**Course relevance:** Week 13 (SYN Flooding, IP Spoofing, Session Hijacking)

> **Remember:** Activate the venv first: `source .venv/bin/activate`

#### C1. Brute Force Attack

```bash
python3 attack_scripts/brute_force.py
```
**Expected:**
- 15 credential pairs tested
- Exactly **3 `[SUCCESS]`** results (alice, bob, admin)
- **12 `[FAIL]`** results
- Summary: "Valid credentials found: 3"

#### C2. IP Spoofing Attack

```bash
python3 attack_scripts/ip_spoof.py --count 20
```
**Expected:**
- 20 requests with forged IP headers from private/test ranges
- Each line shows the forged IP and HTTP status code (HTTP `401` — the gateway rejects them because no JWT token is included, which is expected for an external attack simulation)
- The IDS detects spoofing on *all* gateway-forwarded traffic (see D1 below)

#### C3. SYN Flood Attack (requires sudo)

```bash
sudo python3 attack_scripts/syn_flood.py --count 1000
```
**Expected:** 1000 SYN packets sent with randomised source IPs, progress every 50 packets.

> **Note:** SYN packets operate below the HTTP layer, so they won't appear in Grafana's HTTP metrics. This is expected — the attack demonstrates a transport-layer concept.

**To prove the attack was stopped by the server:**
Because the packets never complete a TCP handshake, the operating system kernel steps in and drops them when the socket listen queue overflows. You can prove the OS successfully defended the server by checking the kernel's `ListenDrops` counter:

```bash
awk 'NR==1 {for(i=1;i<=NF;i++) if($i=="ListenDrops") col=i} NR==2 {print "Kernel Listen Drops (SYN Packets rejected):", $col}' /proc/net/netstat
```
*Run this before and after the attack to show the counter increasing by exactly the number of attack packets!*

#### C3b. Verify graceful no-root handling

```bash
python3 attack_scripts/syn_flood.py
```
**Expected:** Prints error about needing root privileges and exits cleanly (no crash/traceback).

---

### Module D — IDS/IPS & Firewall

#### 💡 What This Demonstrates

The **IDS (Intrusion Detection System)** is a Python middleware (`ids/ids_middleware.py`) bind-mounted into each Flask service. It runs as a `before_request` hook, inspecting every inbound request before application logic executes. It uses **Redis sliding-window counters** (not fixed time buckets) to track request rates per IP.

The IDS detects three types of threats:
1. **Rate anomaly:** IP exceeds 80 requests/60s (alert) or 120 requests/60s (block)
2. **IP spoofing:** `X-Forwarded-For` header contains IPs from private/test ranges
3. **Endpoint hammering:** Same IP hits same path >60 times in 60s

When the block threshold (120 req/60s) is reached, the IDS promotes to **IPS (Intrusion Prevention)**: it adds the IP to a Redis blocklist (`ids:global:blocklist`) using atomic `SADD`, then syncs the blocklist to all 6 APISIX routes via a **distributed lock** (`ids:lock:apisix_sync`, 5s TTL) to prevent race conditions between concurrent service instances.

The **static firewall** pre-blocks known-bad CIDR ranges at the gateway using APISIX's `ip-restriction` plugin. The IPS sync always merges dynamic blocks with these static rules.

**Course relevance:** Week 14 (Firewalls, IDS/IPS, Proxy Servers)

#### D1. Verify IDS detects IP spoofing

The IDS middleware runs inside each Flask service and inspects *every* inbound request that **reaches Flask**. Note that the attack scripts from Module C (ip_spoof.py, brute_force.py) send requests **without a JWT token**, so APISIX rejects them with HTTP 401 at the gateway — they never reach Flask and therefore never trigger IDS logs.

However, when APISIX forwards **authenticated** requests, it adds the client's real IP to `X-Forwarded-For`. Since requests originate from the Docker host, this IP is `172.18.0.x` — a private range (`172.16.0.0/12`) that the IDS flags as potentially spoofed. This demonstrates the IDS inspecting real traffic.

First, send a few authenticated requests to generate IDS logs:

```bash
for i in {1..30}; do
  curl -s http://localhost:9080/users -H "Authorization: Bearer $TOKEN" > /dev/null
done
```

Then check the Flask service logs:

```bash
docker logs secure-microservices-network-users-1 2>&1 | grep -E "\[IDS\]|\[IPS\]" | tail -10
```
**Expected:** `[IDS] WARNING` lines showing "IP spoofing detected" with the Docker gateway IP range (`172.16.0.0/12`). These entries prove the IDS middleware is actively inspecting every forwarded request's headers.

#### D2. Verify Redis stores IDS sliding-window counters

> **⏱️ Timing note:** IDS keys use a 60-second sliding window with a 70-second TTL. You must check Redis **within 70 seconds** of the last request, otherwise the keys will have expired. Run the commands below together:

```bash
# Send an authenticated request so the IDS records it in Redis
curl -s http://localhost:9080/users -H "Authorization: Bearer $TOKEN" > /dev/null

# Immediately check Redis (must be within 70 seconds)
docker exec secure-microservices-network-redis-1 redis-cli keys "ids:*"
```
**Expected:** Keys matching `ids:rate:<ip>` and `ids:ep:<ip>:<path>` — these are the sliding-window sorted sets. For example:
```
ids:rate:172.18.0.12
ids:ep:172.18.0.12:/users
```

You can also inspect the TTL to see the countdown:
```bash
docker exec secure-microservices-network-redis-1 redis-cli ttl "ids:rate:172.18.0.12"
```

#### D3. Verify static firewall CIDRs are configured

The firewall operates on the **real source IP** (`remote_addr`), not on spoofable headers like `X-Forwarded-For` — this is by design, otherwise attackers could bypass the firewall by simply not sending that header. To verify the firewall is configured:

```bash
# Check the ip-restriction plugin on a route
curl -s http://localhost:9180/apisix/admin/routes/users_root \
  -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" | python3 -c "
import sys, json
d = json.load(sys.stdin)
bl = d.get('value',{}).get('plugins',{}).get('ip-restriction',{}).get('blacklist',[])
print(f'Blocked CIDRs: {bl}')
"
```
**Expected:** `['203.0.113.0/24', '198.51.100.0/24', '100.64.0.0/10']` — Three CIDR ranges blocked on all 6 routes.

#### D4. Test rate limiting (100 req/60s per IP)

```bash
for i in $(seq 1 105); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9080/auth/verify)
  if [ "$CODE" == "429" ]; then
    echo "Rate limited at request $i (HTTP 429)"
    break
  fi
done
```
**Expected:** Rate limit hit around request 100 with HTTP `429 Too Many Requests`.

#### D5. Trigger IPS auto-block (optional — long-running)

```bash
# Send enough requests to exceed IDS_BLOCK_AT (120 req/60s)
for i in $(seq 1 130); do
  curl -s http://localhost:9080/users -H "Authorization: Bearer $TOKEN" > /dev/null
done

# Check IMMEDIATELY — the blocklist key persists, but check right after the loop
docker exec secure-microservices-network-redis-1 redis-cli smembers ids:global:blocklist
```
**Expected:** The source IP (e.g., `172.18.0.12`) appears in the Redis blocklist. Check logs for `[IPS] Blocked IP ...` messages:
```bash
docker logs secure-microservices-network-users-1 2>&1 | grep "\[IPS\]" | tail -5
```

---

### Observability — Grafana Dashboards

#### 💡 What This Demonstrates

Prometheus scrapes metrics from all Flask services **over mTLS** — it presents its own certificate (`prometheus.crt`) and verifies each service's certificate against the project CA. This means even the monitoring pipeline is encrypted and authenticated.

Grafana visualises these metrics in real-time. The 4 new security panels show the impact of attacks and authentication patterns, while the original 4 panels continue to show application-level metrics.

**Course relevance:** Week 7 (Data Centre Networking), Week 10 (Microservice Architecture)

#### Open Grafana

```
URL:   http://localhost:3000
Login: admin / admin
Path:  Dashboards → Flask Services Monitoring
```

#### 8 Unified Dashboard Panels

The dashboard provides a complete, unified view of both application performance and network security. Here is exactly what each panel monitors:

**1. Service Requests Per Second**
* **PromQL:** `sum(rate(flask_http_requests_total[1m])) by (service)`
* **Technical:** Measures the live throughput (RPS) of the system, grouped by microservice, using a 1-minute rolling rate.
* **Non-Technical:** Shows exactly how busy the platform is right now. It tells us whether traffic is currently flowing smoothly or flatlining.

**2. Service Request Latency (p95, p99)**
* **PromQL:** `histogram_quantile(0.95, sum(rate(flask_request_latency_seconds_bucket[5m])) by (le, service))`
* **Technical:** Calculates the 95th percentile response times using Prometheus histograms to track SLA compliance.
* **Non-Technical:** Measures real user experience. It guarantees that 95% of customers are experiencing fast, snappy load times and highlights if a specific service is lagging.

**3. HTTP Status Codes by Service**
* **PromQL:** `sum(increase(flask_http_requests_total{http_status=~"2.."}[5m])) by (service)`
* **Technical:** Tracks the distribution of successful (2xx) versus failed (4xx/5xx) HTTP responses over a 5-minute window.
* **Non-Technical:** Highlights system stability. A green bar means operations are succeeding, while red means the server is crashing or failing to handle requests.

**4. Total Requests by Service**
* **PromQL:** `sum(increase(flask_http_requests_total[5m])) by (service)`
* **Technical:** Aggregates the absolute volume of traffic handled by each upstream Docker container.
* **Non-Technical:** Shows a pie-chart breakdown of which part of the business is most popular (e.g., are people browsing products or placing orders?).

**5. IDS/IPS — Auth Failures (Attack Indicator)**
* **PromQL:** `sum(increase(auth_requests_total{status="401"}[5m]))`
* **Technical:** Tracks the absolute volume of unauthorized (HTTP 401) requests rejected by the gateway.
* **Non-Technical:** Acts as our Intrusion Detection early-warning system. A sudden, massive number here immediately flags an active brute-force or credential stuffing attack.

**6. Auth — Token Success vs Failure Rate**
* **PromQL:** `sum(rate(auth_requests_total{status="200"}[1m]))` *(vs 401)*
* **Technical:** Compares the rate of successful authentications against the rate of cryptographic rejections.
* **Non-Technical:** Shows the tug-of-war between legitimate users successfully logging in versus hackers attempting to guess passwords.

**7. Requests by JWT Subject (Non-Repudiation)**
* **PromQL:** `sum(increase(flask_http_requests_total[5m])) by (subject)`
* **Technical:** Groups all backend traffic by the `subject` label, which is securely extracted from the JWT payload at the APISIX gateway.
* **Non-Technical:** Provides absolute cryptographic proof of accountability (Non-Repudiation). It proves exactly which human being performed an action, and they cannot deny it.

**8. Auth Error Rate (Attack Indicator)**
* **PromQL:** `sum(rate(auth_requests_total{status="401"}[1m]))`
* **Technical:** A timeseries visualization of gateway-level 401 rejections over time.
* **Non-Technical:** Visually maps out the timeline of an attack. It allows security teams to see exactly when an automated attack started, peaked, and was mitigated.

#### Verify Prometheus targets

```bash
curl -s 'http://localhost:9090/api/v1/targets' | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data['data']['activeTargets']:
    print(f\"  {t['labels']['job']:12s} → {t['health']}\")
"
```
**Expected:** All 5 targets (`apisix`, `users`, `products`, `orders`, `auth`) show `up`.

---

## 📂 Project Structure

```
Secure-Microservices-Network/
├── certs/
│   └── generate-certs.sh              # TLS certificate generator (CA + 6 service certs)
├── flask/
│   ├── users/     (app.py, Dockerfile, requirements.txt)    # Users microservice
│   ├── products/  (app.py, Dockerfile, requirements.txt)    # Products microservice
│   ├── orders/    (app.py, Dockerfile, requirements.txt)    # Orders microservice
│   └── auth/      (app.py, Dockerfile, requirements.txt)    # Auth microservice (NEW)
├── ids/
│   └── ids_middleware.py               # IDS/IPS middleware (bind-mounted, not baked)
├── attack_scripts/
│   ├── syn_flood.py                    # SYN flood simulation (requires sudo)
│   ├── ip_spoof.py                     # IP spoofing simulation
│   └── brute_force.py                  # Brute-force credential attack
├── apisix_conf/config.yaml             # APISIX config with SSL + trusted CA
├── dashboard_conf/conf.yaml            # APISIX Dashboard config (DO NOT MODIFY)
├── db/init.sql                         # PostgreSQL schema (DO NOT MODIFY)
├── prometheus/prometheus.yml           # Prometheus config with mTLS scraping
├── grafana/provisioning/
│   ├── datasources/prometheus.yml
│   └── dashboards/
│       ├── services-monitoring.json    # Flask dashboard (8 panels)
│       └── apisix-dashboard.json       # APISIX dashboard
├── docker-compose.yml                  # 11 services, 4 volumes, 1 network
├── init-gateway.sh                     # Post-startup APISIX configuration (7 steps)
└── README.md                           # This file
```

---

## 🐳 Service Inventory

| Service | Port (Host) | Purpose |
|---|---|---|
| `apisix` | 9080 (HTTP), 9443 (HTTPS), 9180 (admin), 9091 (metrics) | API Gateway |
| `apisix-dashboard` | 9000 | Gateway admin UI |
| `etcd` | 7000 | APISIX config store |
| `db` | 5432 | PostgreSQL database |
| `redis` | 6379 | IDS rate counters + blocklist |
| `users` | 5001 | Users microservice (mTLS + IDS) |
| `products` | 5002 | Products microservice (mTLS + IDS) |
| `orders` | 5003 | Orders microservice (mTLS + IDS) |
| `auth` | 5004 | JWT auth microservice (mTLS) |
| `prometheus` | 9090 | Metrics collection (mTLS scraping) |
| `grafana` | 3000 | Dashboard UI (admin/admin) |

---

## 📚 Technology Stack

| Component | Technology | Security Role |
|---|---|---|
| API Gateway | Apache APISIX | JWT enforcement, rate limiting, firewall, TLS termination |
| Microservices | Flask 2.3 (Python 3.11) | mTLS server, subject logging, IDS middleware |
| Database | PostgreSQL 15 | Application data persistence |
| Cache/State | Redis 7 | IDS sliding-window counters, global blocklist, distributed lock |
| Auth | PyJWT + HS256 | Token issuing/verification |
| Monitoring | Prometheus + Grafana | mTLS-secured scraping, 8-panel dashboard |
| Encryption | OpenSSL (self-signed CA) | mTLS between all services |
| Orchestration | Docker Compose v2 | 11 containers, bridge network |

---

## 📊 Course Coverage

| Week | Topics | Project Component |
|---|---|---|
| 1 | Network Applications, Protocol Layers | HTTP/HTTPS as application-layer protocol across all services |
| 7 | Data Centre Networking, Middleboxes | APISIX as North–South gateway; inter-service calls as East–West traffic |
| 9 | Cloud Deployment (Private Cloud) | Docker Compose as self-hosted private cloud environment |
| 10 | VMs vs. Containers, Microservices | 4 independently containerised Flask services; IDS as side-loaded module |
| 12 | CIA Triad, Authentication, Non-Repudiation | HTTPS/mTLS (Confidentiality); JWT subject logging (Non-Repudiation) |
| 13 | SSL/TLS, SYN Flooding, IP Spoofing | mTLS between all services; 3 attack simulation scripts |
| 14 | Firewalls, IDS/IPS, Proxy Servers | ip-restriction as static firewall; IDS middleware; IPS auto-blocking |

---

## 🛠️ Troubleshooting

### Docker credential issues
```bash
echo '{}' > ~/.docker/config.json
docker compose build --no-cache
```

### Certificates not found
```bash
bash certs/generate-certs.sh
docker compose restart
```

### Gateway routes not configured
```bash
# Idempotent — safe to run multiple times
bash init-gateway.sh
```

### Prometheus targets showing "down"
```bash
docker exec secure-microservices-network-prometheus-1 ls /certs/
# Should show: ca.crt, prometheus.crt, prometheus.key
```

### Full reset
```bash
docker compose down --volumes
bash certs/generate-certs.sh
docker compose build --no-cache && docker compose up -d
sleep 45
bash init-gateway.sh
```

---

Made with ❤️ by **Shazan**, **Kashan**
