"""
IDS/IPS Middleware — Intrusion Detection and Prevention System
==============================================================
Bind-mounted into users, products, orders containers at /ids/.
Registered as a Flask before_request hook.

Detects: rate anomalies, IP spoofing, endpoint hammering.
Blocks:  auto-blocks IPs exceeding IDS_BLOCK_AT via APISIX ip-restriction.
"""

import os
import time
import logging
import ipaddress
import json
import redis
import requests
from flask import request, abort

logger = logging.getLogger("IDS")
logger.setLevel(logging.WARNING)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s — %(message)s"))
    logger.addHandler(handler)

# ── Configuration (from environment variables) ───────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
IDS_WINDOW = int(os.getenv("IDS_WINDOW", "60"))
IDS_THRESHOLD = int(os.getenv("IDS_THRESHOLD", "80"))
IDS_BLOCK_AT = int(os.getenv("IDS_BLOCK_AT", "120"))
APISIX_ADMIN_URL = os.getenv("APISIX_ADMIN_URL", "http://apisix:9180")
APISIX_API_KEY = os.getenv("APISIX_API_KEY", "edd1c9f034335f136f87ad84b625c8f1")

# Static CIDRs that must never be removed by IPS sync
STATIC_CIDRS = ["203.0.113.0/24", "198.51.100.0/24", "100.64.0.0/10"]

# Private/spoofable IP ranges for detection
SPOOF_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("100.64.0.0/10"),
]

# APISIX route IDs that need firewall updates
ROUTE_IDS = [
    "users_root", "products_root", "orders_root",
    "users_wildcard", "products_wildcard", "orders_wildcard",
]

# ── Redis connection (lazy, with graceful degradation) ───────────────────────
_redis_client = None

def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT,
            decode_responses=True, socket_timeout=2,
            socket_connect_timeout=2,
        )
    return _redis_client


def safe_redis_op(func):
    """Decorator for Redis operations — returns None on failure."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (redis.RedisError, ConnectionError, OSError) as e:
            logger.error(f"Redis unavailable: {e}")
            return None
    return wrapper


# ── Sliding Window Rate Counter ──────────────────────────────────────────────

@safe_redis_op
def record_request(client_ip, path):
    """Record a request in the sliding window and return (total_count, path_count)."""
    r = get_redis()
    now = time.time()
    window_start = now - IDS_WINDOW

    pipe = r.pipeline()

    # Global rate key for this IP
    rate_key = f"ids:rate:{client_ip}"
    pipe.zremrangebyscore(rate_key, 0, window_start)
    pipe.zadd(rate_key, {f"{now}:{id(pipe)}": now})
    pipe.zcard(rate_key)
    pipe.expire(rate_key, IDS_WINDOW + 10)

    # Per-endpoint key for this IP
    ep_key = f"ids:ep:{client_ip}:{path}"
    pipe.zremrangebyscore(ep_key, 0, window_start)
    pipe.zadd(ep_key, {f"{now}:{id(pipe)}:ep": now})
    pipe.zcard(ep_key)
    pipe.expire(ep_key, IDS_WINDOW + 10)

    results = pipe.execute()
    total_count = results[2]   # zcard of rate_key
    path_count = results[6]    # zcard of ep_key

    return total_count, path_count


# ── IP Spoofing Detection ────────────────────────────────────────────────────

def check_ip_spoofing():
    """Check X-Forwarded-For header for spoofed IPs."""
    xff = request.headers.get("X-Forwarded-For", "")
    if not xff:
        return

    for ip_str in xff.split(","):
        ip_str = ip_str.strip()
        try:
            ip_addr = ipaddress.ip_address(ip_str)
            for net in SPOOF_RANGES:
                if ip_addr in net:
                    logger.warning(
                        f"[IDS] IP spoofing detected — "
                        f"X-Forwarded-For contains {ip_str} (range {net}), "
                        f"path={request.path}"
                    )
                    return
        except ValueError:
            continue


# ── IPS Auto-Blocking ────────────────────────────────────────────────────────

@safe_redis_op
def ips_block_ip(client_ip):
    """Add IP to blocklist and sync to APISIX with distributed lock."""
    r = get_redis()

    # Add to Redis blocklist (atomic, idempotent)
    r.sadd("ids:global:blocklist", client_ip)
    logger.warning(f"[IPS] Blocked IP {client_ip} — added to global blocklist")

    # Try to acquire distributed lock for APISIX sync
    lock_key = "ids:lock:apisix_sync"
    lock_acquired = r.set(lock_key, "locked", nx=True, ex=5)

    if not lock_acquired:
        # Another service is syncing — skip (IP is already in Redis)
        return

    try:
        # Read full blocklist from Redis
        blocked_ips = r.smembers("ids:global:blocklist")
        # Merge with static CIDRs
        full_blocklist = list(set(STATIC_CIDRS) | set(blocked_ips))

        # Sync to all 6 APISIX routes
        sync_blocklist_to_apisix(full_blocklist)
    except Exception as e:
        logger.error(f"[IPS] APISIX sync error: {e}")
    finally:
        # Lock auto-expires via TTL, but clean up if we can
        try:
            r.delete(lock_key)
        except Exception:
            pass


def sync_blocklist_to_apisix(blocklist):
    """Write the merged blocklist to all 6 APISIX routes."""
    headers = {
        "X-API-KEY": APISIX_API_KEY,
        "Content-Type": "application/json",
    }

    for route_id in ROUTE_IDS:
        try:
            # Fetch current route to preserve existing plugins
            resp = requests.get(
                f"{APISIX_ADMIN_URL}/apisix/admin/routes/{route_id}",
                headers=headers, timeout=2
            )
            if resp.status_code != 200:
                continue

            data = resp.json()
            # Handle APISIX response format
            if "value" in data:
                plugins = data["value"].get("plugins", {})
            elif "node" in data:
                plugins = data["node"]["value"].get("plugins", {})
            else:
                plugins = data.get("plugins", {})

            # Update ip-restriction plugin
            plugins["ip-restriction"] = {
                "blacklist": blocklist,
                "message": "Blocked by firewall"
            }

            # PATCH the route with updated plugins
            requests.patch(
                f"{APISIX_ADMIN_URL}/apisix/admin/routes/{route_id}",
                headers=headers, json={"plugins": plugins}, timeout=2
            )
            logger.warning(f"[IPS] Synced blocklist to route {route_id}")

        except (requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"[IPS] APISIX sync timeout for {route_id}: {e}")
        except Exception as e:
            logger.error(f"[IPS] APISIX sync error for {route_id}: {e}")


# ── Main Middleware Hook ─────────────────────────────────────────────────────

def ids_check():
    """Flask before_request hook — runs on every inbound request."""
    # Skip metrics/health to avoid noise
    if request.path in ("/metrics", "/health"):
        return

    client_ip = request.remote_addr or "unknown"

    # 1. Check for IP spoofing in headers
    check_ip_spoofing()

    # 2. Record request and check rate limits
    result = record_request(client_ip, request.path)
    if result is None:
        # Redis unavailable — allow request to pass (NFR-012)
        return

    total_count, path_count = result

    # 3. Endpoint hammering detection (>60 same path in window)
    if path_count > 60:
        logger.warning(
            f"[IDS] Endpoint hammering detected — "
            f"IP={client_ip}, path={request.path}, "
            f"count={path_count}/{IDS_WINDOW}s"
        )

    # 4. Rate anomaly detection
    if total_count > IDS_BLOCK_AT:
        logger.warning(
            f"[IDS] Rate anomaly (BLOCK threshold) — "
            f"IP={client_ip}, count={total_count}/{IDS_WINDOW}s"
        )
        ips_block_ip(client_ip)
    elif total_count > IDS_THRESHOLD:
        logger.warning(
            f"[IDS] Rate anomaly (alert threshold) — "
            f"IP={client_ip}, count={total_count}/{IDS_WINDOW}s"
        )


def register_ids(app):
    """Register the IDS middleware as a before_request hook on a Flask app."""
    app.before_request(ids_check)
