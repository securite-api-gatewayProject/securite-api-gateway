"""
ip_blocker.py

Fetch malicious IPs from public feeds and push to Kong ip-restriction plugin.

Usage examples:
    python ip_blocker.py --fetch
    python ip_blocker.py --simulate --daemon 60
    python ip_blocker.py --list

Saves blocked IPs to `blocked_ips.json` in the same folder.
"""
from __future__ import annotations
import requests
import ipaddress
import time
import json
from pathlib import Path
from typing import List

FEED_FEODO = "https://feodotracker.abuse.ch/downloads/ipblocklist.txt"
FEED_ET = "https://rules.emergingthreats.net/blockrules/compromised-ips.txt"
KONG_ADMIN = "http://localhost:8001"
BLOCKED_FILE = Path(__file__).parent / "blocked_ips.json"


def _fetch_feed(url: str) -> List[str]:
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        lines = r.text.splitlines()
        ips = []
        for l in lines:
            l = l.strip()
            if not l or l.startswith("#"):
                continue
            # sometimes rules contain extra tokens, take first token
            tok = l.split()[0]
            try:
                ipaddress.ip_network(tok)
                ips.append(tok)
            except Exception:
                # skip
                continue
        return ips
    except Exception:
        return []


def validate_and_dedupe(ips: List[str]) -> List[str]:
    seen = set()
    out = []
    for ip in ips:
        try:
            ipaddress.ip_address(ip)
            if ip not in seen:
                seen.add(ip)
                out.append(ip)
        except Exception:
            # if network (CIDR), skip for Kong ip-restriction simple demo
            try:
                net = ipaddress.ip_network(ip)
                for a in net.hosts():
                    s = str(a)
                    if s not in seen:
                        seen.add(s)
                        out.append(s)
            except Exception:
                continue
    return out


def push_to_kong(ips: List[str], kong_admin: str = KONG_ADMIN) -> List[str]:
    pushed = []
    for ip in ips:
        payload = {"name": "ip-restriction", "config": {"blacklist": [ip]}}
        try:
            r = requests.post(f"{kong_admin.rstrip('/')}/plugins", json=payload, timeout=5)
            if r.status_code in (200, 201):
                pushed.append(ip)
        except Exception:
            continue
    return pushed


def list_blocked(kong_admin: str = KONG_ADMIN) -> List[dict]:
    try:
        r = requests.get(f"{kong_admin.rstrip('/')}/plugins?name=ip-restriction", timeout=5)
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception:
        return []
    return []


def save_blocked(ips: List[str]):
    BLOCKED_FILE.write_text(json.dumps({"ips": ips}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IP blocker fetching feeds and pushing to Kong")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--daemon", type=int, help="Run as daemon and refresh every N minutes")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        items = list_blocked()
        print(json.dumps(items, indent=2))
        raise SystemExit(0)

    if args.simulate:
        # generate fake IPs for local testing
        fake = [f"192.0.2.{i}" for i in range(1, 20)]
        pushed = push_to_kong(fake)
        save_blocked(pushed)
        print(f"Simulated push: {len(pushed)} IPs")
        if not args.daemon:
            raise SystemExit(0)

    def _run_once():
        ips = []
        ips += _fetch_feed(FEED_FEODO)
        ips += _fetch_feed(FEED_ET)
        ips = validate_and_dedupe(ips)
        pushed = push_to_kong(ips)
        save_blocked(pushed)
        print(f"Pushed {len(pushed)} IPs to Kong")

    if args.daemon:
        try:
            while True:
                _run_once()
                time.sleep(args.daemon * 60)
        except KeyboardInterrupt:
            print("Stopping daemon")
    else:
        _run_once()
