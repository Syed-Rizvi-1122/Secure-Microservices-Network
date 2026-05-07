#!/usr/bin/env python3
"""
IP Spoofing Attack Simulation — Network-Layer (Week 13)
========================================================
Sends HTTP requests with forged X-Forwarded-For, X-Real-IP,
and X-Originating-IP headers to simulate IP spoofing.

Does NOT require sudo.

Usage:
  python3 attack_scripts/ip_spoof.py --count 5
"""

import argparse
import random
import requests


# Forged IP pools from the required ranges
SPOOF_POOLS = [
    # 10.0.0.0/8
    lambda: f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
    # 192.168.0.0/16
    lambda: f"192.168.{random.randint(0,255)}.{random.randint(1,254)}",
    # 203.0.113.0/24 (TEST-NET-3)
    lambda: f"203.0.113.{random.randint(1,254)}",
    # 198.51.100.0/24 (TEST-NET-2)
    lambda: f"198.51.100.{random.randint(1,254)}",
    # 100.64.0.0/10 (Carrier-grade NAT)
    lambda: f"100.{random.randint(64,127)}.{random.randint(0,255)}.{random.randint(1,254)}",
]

ENDPOINTS = ["/users", "/products", "/orders"]


def main():
    parser = argparse.ArgumentParser(description="IP Spoofing Attack Simulation")
    parser.add_argument("--target-ip", default="127.0.0.1", help="Target IP (default: 127.0.0.1)")
    parser.add_argument("--target-port", type=int, default=9080, help="Target port (default: 9080)")
    parser.add_argument("--count", type=int, default=20, help="Number of requests (default: 20)")
    args = parser.parse_args()

    base_url = f"http://{args.target_ip}:{args.target_port}"

    print(f"╔══════════════════════════════════════════╗")
    print(f"║      IP Spoofing Attack Simulation       ║")
    print(f"╠══════════════════════════════════════════╣")
    print(f"║  Target: {base_url}")
    print(f"║  Count:  {args.count} requests")
    print(f"╚══════════════════════════════════════════╝")
    print()

    for i in range(1, args.count + 1):
        # Pick a random IP generator and endpoint
        forged_ip = random.choice(SPOOF_POOLS)()
        endpoint = random.choice(ENDPOINTS)
        url = f"{base_url}{endpoint}"

        headers = {
            "X-Forwarded-For": forged_ip,
            "X-Real-IP": forged_ip,
            "X-Originating-IP": forged_ip,
        }

        try:
            resp = requests.get(url, headers=headers, timeout=5)
            status = resp.status_code
        except requests.RequestException as e:
            status = f"ERROR ({e})"

        print(f"  [{i:3d}/{args.count}] Forged IP: {forged_ip:20s} → {endpoint:12s} → HTTP {status}")

    print()
    print(f"═══════════════════════════════════════════")
    print(f"  IP Spoofing simulation complete.")
    print(f"  Check IDS logs: docker logs <users-container>")
    print(f"  Check Grafana:  http://localhost:3000")
    print(f"═══════════════════════════════════════════")


if __name__ == "__main__":
    main()
