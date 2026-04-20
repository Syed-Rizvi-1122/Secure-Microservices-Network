# PRD — Secure Microservices Network
**Project:** CS4068 Network Protocols and Standards — Semester Project, Spring 2026
**University:** FAST-NUCES Karachi
**Document type:** Product Requirements Document (agent-facing)

---

## 0. Agent Instructions

This document defines **what** to build, not how to build it. Requirements are behavioural and measurable. Implement however you judge best, subject to the constraints in each section. Where a constraint says **MUST**, it is non-negotiable. Where it says **SHOULD**, use your judgement. Do not add services, ports, or dependencies that are not listed here.

---

## 1. Development Environment

| Item | Value |
|---|---|
| Host OS | Windows 11 |
| Container runtime | Docker Desktop with WSL 2 backend |
| Working shell | WSL 2 (Ubuntu) — all commands run inside WSL |
| Compose syntax | `docker compose` (v2, with a space — never `docker-compose`) |
| Python base image | `python:3.11-slim` for all Flask services |
| Target architecture | amd64 / x86-64 |

---

## 2. Existing Repository

**Repo:** `https://github.com/Syed-Rizvi-1122/Distributed-Systems-Networking` — branch `main`

### 2.1 Existing Directory Layout

```
Distributed-Systems-Networking/
├── apisix_conf/config.yaml
├── dashboard_conf/conf.yaml
├── db/init.sql
├── flask/
│   ├── users/    (app.py, Dockerfile, requirements.txt)
│   ├── products/ (app.py, Dockerfile, requirements.txt)
│   └── orders/   (app.py, Dockerfile, requirements.txt)
├── grafana/provisioning/
│   ├── datasources/prometheus.yml
│   └── dashboards/ (apisix-dashboard.json, services-monitoring.json)
├── prometheus/prometheus.yml
├── docker-compose.yml
└── requirements.txt
```

### 2.2 Existing Services

| Service | Internal hostname | Internal port | Host port(s) | Notes |
|---|---|---|---|---|
| `apisix` | `apisix` | 9080 (HTTP), 9443 (HTTPS), 9180 (admin), 9091 (metrics) | 9080, 9443, 9180, 9091, 9092 | API Gateway |
| `apisix-dashboard` | `apisix-dashboard` | 9000 | 9000 | Admin UI |
| `etcd` | `etcd` | 7000 | 7000 | APISIX config store |
| `db` | `db` | 5432 | 5432 | PostgreSQL 15 |
| `users` | `users` | 5000 | 5001 | Flask microservice |
| `products` | `products` | 5000 | 5002 | Flask microservice |
| `orders` | `orders` | 5000 | 5003 | Flask microservice |
| `prometheus` | `prometheus` | 9090 | 9090 | Metrics collection |
| `grafana` | `grafana` | 3000 | 3000 | Dashboard UI |

**Docker network:** `apisix` (bridge). All services are on this network.
**Docker volumes:** `etcd_data`, `prometheus_data`, `grafana_data`

### 2.3 Fixed Values — MUST NOT Change

| Item | Value |
|---|---|
| APISIX Admin API key | `edd1c9f034335f136f87ad84b625c8f1` |
| APISIX Admin API URL (from host) | `http://localhost:9180` |
| APISIX Admin API URL (from inside Docker) | `http://apisix:9180` |
| PostgreSQL credentials | user: `postgres`, password: `password`, db: `ecommerce` |
| PostgreSQL DSN | `postgresql://postgres:password@db:5432/ecommerce` |
| Grafana credentials | `admin` / `admin` |
| Flask service internal port | `5000` (all three services) |
| JWT secret | `nps-project-secret-2026` |
| JWT algorithm | `HS256` |
| Token TTL | `3600` seconds |

### 2.4 What Each Existing Flask Service Already Does

Each of `users`, `products`, and `orders` already provides:
- `POST /<service>` — creates a record in PostgreSQL
- `GET /<service>` — lists all records
- `GET /health` — returns `{"status": "ok"}`
- `GET /metrics` — Prometheus metrics via `prometheus_client`, including `flask_http_requests_total` (Counter) and `flask_request_latency_seconds` (Histogram)

### 2.5 Constraints on Existing Files

- **MUST NOT** rename any existing service in `docker-compose.yml`
- **MUST NOT** change the internal port of any existing Flask service
- **MUST NOT** modify `dashboard_conf/conf.yaml`
- **MUST NOT** modify `db/init.sql`
- **MUST NOT** remove or alter existing Prometheus scrape targets in `prometheus/prometheus.yml`
- **MUST NOT** remove or alter existing Grafana dashboard panels — only add new ones

---

## 3. New Services to Add

Two new services must be added to `docker-compose.yml`:

### 3.1 `auth` Service

A new Flask microservice responsible for issuing and verifying JWT tokens.

**Container config:**
- Build from a new `flask/auth/` directory
- Internal port: `5000`
- Host port: `5004`
- Network: `apisix`
- Environment variables: `JWT_SECRET`, `TOKEN_TTL_SECONDS`, `SERVICE_NAME=auth`
- Must have access to the `certs/` directory (read-only bind-mount to `/certs`)

**Required endpoints:**

| Endpoint | Method | Auth required | Description |
|---|---|---|---|
| `/auth/token` | POST | No | Accepts `{"username": string, "password": string}`. Returns `{"token": string, "expires_in": int}` on success, `401` on invalid credentials. |
| `/auth/verify` | GET | Bearer token in `Authorization` header | Returns `{"valid": true, "sub": string}` if token is valid; `401` otherwise. |
| `/health` | GET | No | Returns `{"status": "ok", "service": "auth"}` |
| `/metrics` | GET | No | Prometheus metrics exposition |

**Hardcoded credential store** (no database required for auth):

| Username | Password |
|---|---|
| `alice` | `password123` |
| `bob` | `securepass` |
| `admin` | `adminpass` |

**Prometheus metrics the auth service MUST export:**
- `auth_requests_total` — Counter, labels: `endpoint`, `status` (HTTP status code as string)

### 3.2 `redis` Service

A Redis instance used by the IDS middleware for rate-counter storage.

**Container config:**
- Image: `redis:7-alpine`
- Internal port: `6379`
- Host port: `6379`
- Network: `apisix`
- Persistent volume: `redis_data`

---

## 4. Module A — End-to-End Encryption

### 4.1 Certificate Requirements

A `certs/` directory must be created at the repo root. It must contain a shell script (`generate-certs.sh`) that, when executed inside WSL, uses `openssl` to produce:

- A self-signed Certificate Authority (CA), 2048-bit RSA, 365-day validity
- One signed certificate + private key for each of: `apisix`, `users`, `products`, `orders`, `auth`, `prometheus`
- The CA common name MUST be `NPS-Project-CA`
- Each service cert's CN MUST match its service name exactly (e.g., CN=`users`)

All `.key` and `.crt` files MUST be added to `.gitignore`. Only the script is committed.

All generated certs live at `certs/<name>.crt` and `certs/<name>.key` on the host, and are bind-mounted read-only to `/certs/` inside any container that needs them.

> **Pre-condition:** `generate-certs.sh` MUST be run successfully before `docker compose up` is executed. If `certs/` is empty when the stack starts, the bind-mounts will mount an empty directory and the APISIX SSL registration will fail silently. There is no automatic retry — cert files must exist on disk before the stack comes up.

### 4.2 APISIX HTTPS

**Requirement:** APISIX MUST serve HTTPS on port `9443` using the `apisix.crt` / `apisix.key` certificate pair.

- TLS versions allowed: TLSv1.2 and TLSv1.3 only
- The SSL configuration block must be added to `apisix_conf/config.yaml` without removing any existing keys

**Acceptance:** `curl -k https://localhost:9443/users/health` returns HTTP 200.

### 4.3a Post-Startup Gateway Initialisation Script

**Requirement:** A script `init-gateway.sh` MUST be created at the repo root. It MUST be idempotent (safe to run multiple times without creating duplicate entries) and MUST be run once after `docker compose up` completes.

The script is responsible for ALL post-startup APISIX configuration. Consolidating this into one script prevents the fragile inline cert embedding and scattered curl steps that would otherwise live across multiple sections. The script MUST perform the following operations in order:

| Step | What it configures | APISIX Admin API endpoint |
|---|---|---|
| 1 | Register the APISIX TLS certificate (reads `certs/apisix.crt` and `certs/apisix.key`, encodes them correctly for JSON) with SNIs `localhost` and `apisix` | `PUT /apisix/admin/ssls/1` |
| 2 | Register upstreams for all four services (`users`, `products`, `orders`, `auth`) — each upstream MUST include a TLS client certificate block pointing to `apisix.crt` / `apisix.key` so APISIX can satisfy Flask's server-side mTLS requirement | `PUT /apisix/admin/upstreams/<id>` |
| 3 | Register public auth routes (`/auth/token`, `/auth/verify`) with no authentication plugins | `PUT /apisix/admin/routes/<id>` |
| 4 | Register a JWT consumer with key `nps-jwt-key` and secret `nps-project-secret-2026` | `PUT /apisix/admin/consumers/nps_user` |
| 5 | Register protected service routes (`/users`, `/products`, `/orders` and wildcard variants) with `jwt-auth` and `limit-count` plugins | `PUT /apisix/admin/routes/<id>` |
| 6 | Apply static firewall CIDR blocklist (`203.0.113.0/24`, `198.51.100.0/24`, `100.64.0.0/10`) to all six service routes | `PUT /apisix/admin/routes/<id>` (update existing) |

The script MUST print a success or failure message for each step. It MUST use the fixed API key `edd1c9f034335f136f87ad84b625c8f1` for all requests.

### 4.3 Mutual TLS Between Flask Services

**Requirement — Caller side:** When any Flask service makes an HTTP call to another Flask service, the call MUST use mutual TLS:
- The calling service presents its own certificate (`/certs/<service_name>.crt` + `.key`)
- The calling service verifies the peer against `/certs/ca.crt`

**Requirement — Server side (critical):** Each Flask service MUST be configured to run its HTTP server with SSL enabled and MUST require and verify a client certificate from every caller. A connection that does not present a certificate signed by the project CA MUST be rejected at the TLS handshake level. This is what makes TLS *mutual* — both parties authenticate each other. Without this server-side enforcement, any client without a cert can still connect and the "mTLS" is effectively one-way TLS only.

**Knock-on effect on APISIX:** Because Flask services now require client certs from all callers, APISIX MUST present its own certificate (`apisix.crt` / `apisix.key`) when forwarding requests upstream to Flask. Each APISIX upstream definition MUST be configured with a TLS client certificate so it can satisfy the Flask server-side verification. This configuration is applied via the APISIX Admin API on each upstream object (not in `config.yaml`).

Each Flask service MUST know its own name via an environment variable `SERVICE_NAME` set in `docker-compose.yml`.

---

## 5. Module B — JWT Authentication and Non-Repudiation

### 5.1 Gateway-Level JWT Enforcement

**Requirement:** The APISIX `jwt-auth` plugin MUST be enabled on all three service routes (`/users`, `/products`, `/orders` and their wildcard variants). Any request missing a valid JWT MUST be rejected with HTTP 401.

- The `/auth/token` and `/auth/verify` routes MUST be publicly accessible (no JWT required)
- A JWT consumer MUST be registered in APISIX with key `nps-jwt-key` and secret `nps-project-secret-2026`
- Rate limiting MUST be preserved on all protected routes (100 req/60s per IP, 429 on breach)
- The `jwt-auth` plugin MUST be configured with `hide_credentials: true` on all protected routes. This strips the raw `Authorization` header before forwarding to Flask — the upstream service receives no JWT, only the verified identity claim injected by APISIX (see below)
- Step 5 of `init-gateway.sh` MUST configure the protected routes to inject the `X-Authenticated-User` header into every upstream request. The value of this header MUST be the `sub` claim extracted from the validated JWT. Flask services MUST read the subject from this header (not by re-parsing the `Authorization` header, which will not be present)

**Acceptance:** A request to `GET /users` without a token returns `401`. The same request with a valid token (obtained from `POST /auth/token`) returns `200`.

### 5.2 Non-Repudiation via JWT Subject Logging

**Requirement:** The `flask_http_requests_total` counter in each of the three existing Flask services MUST be updated to include a `subject` label.

- The `subject` label MUST be populated by reading the `X-Authenticated-User` request header, which is injected by APISIX after validating the JWT (see §5.1). Flask MUST NOT attempt to parse the `Authorization` header for this purpose — that header is stripped by APISIX before the request reaches Flask
- If the `X-Authenticated-User` header is absent (e.g., request came via direct service port rather than the gateway), `subject` MUST be set to the string `"anonymous"`
- This label MUST appear in the Prometheus metrics output at `GET /metrics`

**Acceptance:** After making authenticated requests as `alice`, the Prometheus query `flask_http_requests_total{subject="alice"}` returns a non-zero value.

---

## 6. Module C — Attack Simulation Scripts

Three Python scripts MUST be created in an `attack_scripts/` directory at the repo root. They run **outside Docker, inside WSL** and require `pip install scapy==2.5.0 requests==2.31.0` in WSL.

### 6.1 `attack_scripts/syn_flood.py`

**Purpose:** Simulate a transport-layer SYN flood (Week 13).

**Requirements:**
- Uses Python raw sockets (`AF_INET`, `SOCK_RAW`, `IPPROTO_TCP`) — requires `sudo`
- Sends TCP SYN packets with randomised source IPs and source ports to a configurable target
- Accepts CLI arguments: `--target-ip` (default `127.0.0.1`), `--target-port` (default `9080`), `--count` (default `500`)
- Prints progress every 50 packets
- Prints a final message pointing the user to Grafana at `http://localhost:3000`
- Gracefully prints an error message and exits (does not crash) if run without root

> **Observability note:** Raw TCP SYN packets that never complete the three-way handshake will not reach the Flask application layer and therefore will NOT appear in Grafana's `flask_http_requests_total` metrics. This is expected behaviour — the SYN flood demonstrates a network/transport-layer concept that operates below the HTTP observability stack. To observe the attack's impact, check OS-level metrics or use `--target-ip <docker-internal-ip>` to target the APISIX container's Docker bridge IP directly (find it with `docker inspect apisix | grep IPAddress`).

### 6.2 `attack_scripts/ip_spoof.py`

**Purpose:** Demonstrate network-layer IP spoofing (Week 13).

**Requirements:**
- Sends HTTP requests with injected `X-Forwarded-For`, `X-Real-IP`, and `X-Originating-IP` headers set to forged private/test IP addresses
- The forged IPs MUST include addresses from these ranges: `10.0.0.0/8`, `192.168.0.0/16`, `203.0.113.0/24`, `198.51.100.0/24`, `100.64.0.0/10`
- Accepts CLI arguments: `--target-ip` (default `127.0.0.1`), `--target-port` (default `9080`), `--count` (default `20`)
- Prints the forged IP and HTTP response code for each request
- Does not require `sudo`

### 6.3 `attack_scripts/brute_force.py`

**Purpose:** Simulate a transport-layer session/credential attack (Week 13).

**Requirements:**
- Sends `POST /auth/token` requests cycling through a hardcoded wordlist of username/password pairs
- The wordlist MUST include at least 12 pairs, of which exactly 3 MUST succeed (matching the credentials defined in §3.1)
- Accepts CLI arguments: `--target-url` (default `http://localhost:9080`), `--delay` (default `0.1` seconds between attempts)
- Prints `[SUCCESS]` for valid credentials, showing the first 30 characters of the returned token
- Prints `[FAIL]` for rejected credentials
- Prints a summary of how many valid credentials were found

---

## 7. Module D — IDS/IPS Middleware and Firewall

### 7.1 IDS Middleware

A Python module MUST be created at `ids/ids_middleware.py`. It is NOT baked into any Docker image — it is bind-mounted read-only from `./ids/` on the host to `/ids/` inside the `users`, `products`, and `orders` containers.

Each of the three existing Flask services MUST register this middleware as a `before_request` hook.

**Detection requirements — the middleware MUST detect and log all of the following:**

| Threat | Detection logic | Log level |
|---|---|---|
| Rate anomaly (alert) | IP exceeds `IDS_THRESHOLD` requests within `IDS_WINDOW` seconds | WARNING |
| Rate anomaly (block) | IP exceeds `IDS_BLOCK_AT` requests within `IDS_WINDOW` seconds | WARNING + IPS action |
| IP spoofing | `X-Forwarded-For` header contains an IP belonging to any of these ranges: `10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`, `203.0.113.0/24`, `198.51.100.0/24`, `100.64.0.0/10`. Detection is based on the header value alone — do NOT check `remote_addr` against `localhost`. Inside Docker, `remote_addr` will be the APISIX container's internal IP (a `172.x.x.x` address), never `127.0.0.1`. | WARNING |
| Endpoint hammering | Same IP hits the same path more than 60 times within `IDS_WINDOW` seconds | WARNING |

**Rate counter storage:** Redis (service `redis`, host configurable via env var `REDIS_HOST`, default `redis`; port via `REDIS_PORT`, default `6379`). Use a sliding-window approach (not a fixed bucket).

**Environment variables the middleware MUST read:**

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `IDS_WINDOW` | `60` | Sliding window size in seconds |
| `IDS_THRESHOLD` | `80` | Requests/window to trigger alert |
| `IDS_BLOCK_AT` | `120` | Requests/window to trigger block |
| `APISIX_ADMIN_URL` | `http://apisix:9180` | APISIX Admin API base URL |
| `APISIX_API_KEY` | `edd1c9f034335f136f87ad84b625c8f1` | APISIX Admin API key |

All six environment variables MUST be set on the `users`, `products`, and `orders` services in `docker-compose.yml`.

> **Rate limiting layer clarification:** Two independent rate limits coexist and are intentional. APISIX enforces a hard limit of 100 req/60s per IP at the gateway (returns HTTP 429). The IDS middleware alerts at 80 req/60s and blocks at 120 req/60s at the application layer. These thresholds are deliberately different: the IDS provides early behavioural warning (at 80) before the gateway hard-blocks (at 100), and the IDS auto-block (at 120) kicks in for traffic that somehow bypasses or races the gateway limit. The gateway limit is the primary traffic control; the IDS is the behavioural anomaly detector.

### 7.2 IPS Auto-Blocking

**Requirement:** When the block threshold is reached, the middleware MUST add the offending IP to a blocklist and ensure APISIX enforces it.

**Global blocklist in Redis (authoritative):** The canonical blocklist MUST be stored in a Redis `SET` at the key `ids:global:blocklist`. Use Redis `SADD` to add IPs — this operation is atomic, so multiple services adding the same IP concurrently is safe and idempotent.

**APISIX sync with distributed lock:** When syncing the blocklist to APISIX, the middleware MUST acquire a Redis distributed lock before reading the list from Redis and writing it to APISIX. The lock key MUST be `ids:lock:apisix_sync` with a TTL of **5 seconds**. If the lock cannot be acquired (another service instance is already syncing), the sync attempt MUST be skipped silently — the IP is already in Redis and will be synced on the next trigger. This prevents the race condition where two services simultaneously `GET` the APISIX route config, each append an IP to their local copy, and one `PUT` overwrites the other's addition.

**Why this matters:** The APISIX Admin API `PUT` is state-replacing, not state-appending. Without a lock, concurrent writes from multiple services will cause one update to silently overwrite another, leaving some blocked IPs unblocked.

**APISIX sync behaviour:**
- Read the full blocklist from Redis `SADD ids:global:blocklist`
- Write the complete list to all six routes: `users_root`, `products_root`, `orders_root`, `users_wildcard`, `products_wildcard`, `orders_wildcard`
- The sync MUST NOT remove IPs that were added by `init-gateway.sh` (the static CIDR ranges) — merge Redis list with static CIDRs before writing
- The APISIX Admin API call MUST have a maximum timeout of **2 seconds**. Timeout or failure MUST be logged but MUST NOT crash or block the in-flight Flask request

**Acceptance:** After running the brute-force script long enough to exceed `IDS_BLOCK_AT`, `docker logs` on any Flask service shows `[IPS] Blocked IP ...`, and `redis-cli smembers ids:global:blocklist` returns at least one IP.

### 7.3 Static Firewall Rules

**Requirement:** The following CIDR ranges MUST be configured as a static `ip-restriction` blocklist on all six service routes:

- `203.0.113.0/24`
- `198.51.100.0/24`
- `100.64.0.0/10`

This is applied as Step 6 of `init-gateway.sh` (see §4.3a). The IPS sync logic (§7.2) MUST preserve these static CIDRs when it writes dynamic IP blocks — it MUST merge both lists before each APISIX `PUT`.

---

## 8. Grafana Dashboard Updates

**Requirement:** Four new panels MUST be added to the existing `grafana/provisioning/dashboards/services-monitoring.json`. Existing panels MUST NOT be removed or modified. Panel IDs must not conflict with existing ones.

| Panel | Type | Prometheus query |
|---|---|---|
| IDS/IPS — Rate-limited requests | `stat` | `sum(increase(flask_http_requests_total{http_status="429"}[5m]))` |
| Auth — Token success vs failure rate | `timeseries` | `sum(rate(auth_requests_total{status="200"}[1m]))` and `sum(rate(auth_requests_total{status="401"}[1m]))` |
| Requests by JWT Subject (Non-Repudiation) | `piechart` | `sum(increase(flask_http_requests_total[5m])) by (subject)` |
| Error rate 4xx+5xx (attack indicator) | `timeseries` | `sum(rate(flask_http_requests_total{http_status=~"(4\|5).."}[1m])) by (service)` |

---

## 9. Prometheus Configuration

**Requirement:** Because all Flask services now run with HTTPS and require client certificates (`CERT_REQUIRED`), Prometheus is a mTLS-protected caller and MUST be configured accordingly. Without this, all scrape jobs for Flask services will fail at the TLS handshake and every Grafana panel will be empty.

The following changes MUST be made to `prometheus/prometheus.yml`:

**1. Add the `auth` scrape job** — Target: `auth:5000`, Job name: `auth`. Must include the same `tls_config` as the other Flask jobs below.

**2. Update all Flask service scrape jobs** (`users`, `products`, `orders`, and the new `auth` job) to:
- Use `https` scheme (not `http`)
- Include a `tls_config` block that specifies:
  - The Prometheus client certificate: `/certs/prometheus.crt`
  - The Prometheus client private key: `/certs/prometheus.key`
  - The CA certificate for peer verification: `/certs/ca.crt`

The APISIX scrape job (`apisix:9091`) scrapes the APISIX metrics endpoint which does not require mTLS, so it MUST remain as plain `http` with no `tls_config`.

**Acceptance:** `curl http://localhost:9090/api/v1/targets` returns all Flask service targets with `"health": "up"`. If any Flask target shows `"health": "down"` with a TLS error, the tls_config is misconfigured.

---

## 10. Final Service Inventory

After all changes, `docker-compose.yml` MUST define exactly these services, volumes, and networks:

**Services:** `apisix-dashboard`, `apisix`, `etcd`, `db`, `redis`, `users`, `products`, `orders`, `auth`, `prometheus`, `grafana`

**Volumes:** `etcd_data`, `prometheus_data`, `grafana_data`, `redis_data`

**Networks:** `apisix` (bridge)

**New volume mounts required on `users`, `products`, `orders`, `auth`:**
- `./certs:/certs:ro`
- `./ids:/ids:ro` (on `users`, `products`, `orders` only — not `auth`)

**`apisix` must also have:**
- `./certs:/certs:ro`

**`prometheus` must also have:**
- `./certs:/certs:ro`

---

## 11. Acceptance Criteria

The project is complete when all of the following pass:

| # | Test | Expected result |
|---|---|---|
| A1 | `curl -k https://localhost:9443/users/health` | HTTP 200, body `{"status":"ok"}` |
| A2 | `curl http://localhost:9080/users/health` | HTTP 200 (HTTP still works) |
| A3 | `curl https://localhost:5001/users` (direct to Flask host port, no client cert) | Connection fails with a TLS error — confirms server-side mTLS is enforced at the Flask socket level, not only at the gateway |
| B1 | `curl -X POST http://localhost:9080/auth/token -d '{"username":"alice","password":"password123"}' -H 'Content-Type: application/json'` | HTTP 200, body contains `token` field |
| B2 | `curl http://localhost:9080/users` (no token) | HTTP 401 |
| B3 | `curl http://localhost:9080/users -H "Authorization: Bearer <valid_token>"` | HTTP 200 |
| B4 | Prometheus query `flask_http_requests_total{subject="alice"}` after authenticated requests | Non-zero value |
| C1 | `python3 attack_scripts/brute_force.py` | Finds 3 valid credentials, prints `[SUCCESS]` for each |
| C2 | `python3 attack_scripts/ip_spoof.py --count 5` | Sends 5 requests, prints forged IP and status code per request |
| C3 | `sudo python3 attack_scripts/syn_flood.py --count 50` | Sends 50 SYN packets, prints progress |
| D1 | `docker logs <users-container> 2>&1 \| grep IDS` after running attack scripts | Shows `[IDS]` warning lines |
| D2 | `docker exec <redis-container> redis-cli keys "ids:*"` | Returns at least one key |
| D2b | `docker exec <redis-container> redis-cli smembers ids:global:blocklist` after running brute-force script | Returns at least one blocked IP address |
| D3 | Grafana at `http://localhost:3000` → Flask Services Monitoring | All 4 new panels visible and populated |

---

## 12. File Change Summary

| File | Action |
|---|---|
| `certs/generate-certs.sh` | CREATE |
| `certs/*.crt`, `certs/*.key` | GITIGNORED (generated, not committed) |
| `flask/auth/app.py` | CREATE |
| `flask/auth/Dockerfile` | CREATE |
| `flask/auth/requirements.txt` | CREATE |
| `ids/ids_middleware.py` | CREATE |
| `attack_scripts/syn_flood.py` | CREATE |
| `attack_scripts/ip_spoof.py` | CREATE |
| `attack_scripts/brute_force.py` | CREATE |
| `init-gateway.sh` | CREATE (idempotent post-startup APISIX configuration script — see §4.3a) |
| `docker-compose.yml` | MODIFY (add `auth`, `redis`; add env vars and volume mounts to existing services) |
| `apisix_conf/config.yaml` | MODIFY (add `ssl:` block only) |
| `prometheus/prometheus.yml` | MODIFY (add `auth` scrape target; switch Flask jobs to `https` with `tls_config` — see §9) |
| `flask/users/app.py` | MODIFY (register IDS middleware; add `subject` label to metrics) |
| `flask/products/app.py` | MODIFY (same as users) |
| `flask/orders/app.py` | MODIFY (same as users) |
| `flask/users/requirements.txt` | MODIFY (ensure `redis`, `PyJWT`, `requests` are included) |
| `flask/products/requirements.txt` | MODIFY (same) |
| `flask/orders/requirements.txt` | MODIFY (same) |
| `grafana/.../services-monitoring.json` | MODIFY (append 4 panels) |
| `.gitignore` | MODIFY (add cert exclusions) |
| `dashboard_conf/conf.yaml` | DO NOT TOUCH |
| `db/init.sql` | DO NOT TOUCH |
