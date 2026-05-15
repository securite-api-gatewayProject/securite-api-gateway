"""
ip_manager.py

Progressive IP banning manager with TTL and Kong Admin API integration.

Usage (CLI):
    python ip_manager.py --action status

Functions provided for programmatic use by `anomaly_detector.py`.
"""
from __future__ import annotations
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional
import datetime

DEFAULT_KONG = "http://localhost:8001"
EVENTS_FILE = Path(__file__).parent / "ip_events.json"


class IPManager:
    def __init__(self, kong_admin: str = DEFAULT_KONG):
        self.kong = kong_admin.rstrip("/")
        self.events = self._load()

    def _load(self) -> Dict[str, Any]:
        if EVENTS_FILE.exists():
            try:
                return json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        EVENTS_FILE.write_text(json.dumps(self.events, default=str, indent=2), encoding="utf-8")

    def _now(self) -> str:
        return datetime.datetime.utcnow().isoformat() + "Z"

    def record_detection(self, ip: str, reason: str = "anomaly", auto_block: bool = True) -> Dict[str, Any]:
        rec = self.events.get(ip, {"count": 0, "actions": []})
        rec["count"] += 1
        action = None
        ttl = None
        count = rec["count"]
        if count == 1:
            action = "MONITOR"
        elif count == 2:
            action = "RATE_LIMIT"
            ttl = 10 * 60
        elif count == 3:
            action = "BLOCK"
            ttl = 60 * 60
        else:
            action = "BLOCK_PERM"
            ttl = None

        entry = {"ts": self._now(), "action": action, "reason": reason, "ttl": ttl}
        rec["actions"].append(entry)
        if ttl:
            entry["expires_at"] = (datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl)).isoformat() + "Z"

        self.events[ip] = rec
        if auto_block and action.startswith("BLOCK"):
            plugin_id = self._apply_kong_block(ip)
            entry["plugin_id"] = plugin_id
        self._save()
        return entry

    def _apply_kong_block(self, ip: str) -> Optional[str]:
        # Create an ip-restriction plugin with the ip in blacklist
        url = f"{self.kong}/plugins"
        payload = {"name": "ip-restriction", "config": {"blacklist": [ip]}}
        try:
            r = requests.post(url, json=payload, timeout=5)
            if r.status_code in (200, 201):
                return str(r.json().get("id"))
        except Exception:
            return None
        return None

    def auto_unblock(self):
        changed = False
        now = datetime.datetime.utcnow()
        for ip, rec in list(self.events.items()):
            for a in list(rec.get("actions", [])):
                exp = a.get("expires_at")
                if exp:
                    try:
                        exp_dt = datetime.datetime.fromisoformat(exp.replace("Z", "+00:00"))
                        if exp_dt <= now:
                            # attempt to remove plugin if recorded
                            pid = a.get("plugin_id")
                            if pid:
                                try:
                                    requests.delete(f"{self.kong}/plugins/{pid}", timeout=5)
                                except Exception:
                                    pass
                            rec["actions"].remove(a)
                            changed = True
                    except Exception:
                        # malformed timestamp or deletion error; skip this action
                        continue
            # if no actions left and count small, keep record; otherwise keep for audit
            self.events[ip] = rec
        if changed:
            self._save()

    def list_events(self) -> Dict[str, Any]:
        return self.events


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IP Manager CLI for progressive banning and Kong integration")
    parser.add_argument("--action", choices=["status", "cleanup", "record"], default="status")
    parser.add_argument("--ip", help="IP to record (for record action)")
    args = parser.parse_args()
    im = IPManager()
    if args.action == "status":
        print(json.dumps(im.list_events(), indent=2))
    elif args.action == "cleanup":
        im.auto_unblock()
        print("Cleanup done")
    elif args.action == "record":
        if not args.ip:
            print("--ip is required for record")
        else:
            print(json.dumps(im.record_detection(args.ip, reason="manual"), indent=2))
