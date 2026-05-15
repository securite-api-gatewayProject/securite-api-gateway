"""
feature_extractor.py

CLI / Importable utilities to parse Suricata eve.json, Kong access logs,
and attack logs (sql/xss). Extracts features per request for the detectors.

Usage (CLI):
    python feature_extractor.py --suricata infra/suricata/logs/eve.json

Functions:
    parse_suricata(path) -> list[dict]
    parse_attack_logs(path) -> list[dict]
    extract_features(events) -> X, meta

This module is importable by `anomaly_detector.py`.
"""
from __future__ import annotations
import json
import math
from collections import defaultdict, deque
from pathlib import Path
from typing import List, Dict, Tuple, Any
import datetime

TYPICAL_METHODS = {"GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"}


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    probs = [float(s.count(c)) / len(s) for c in set(s)]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def parse_suricata(path: str) -> List[Dict[str, Any]]:
    """Parse Suricata eve.json (JSON lines). Return list of events with normalized fields.

    Each event contains: ts (datetime), src_ip, dest_ip, http: {method, url, status, body}
    """
    events = []
    p = Path(path)
    if not p.exists():
        return events
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("event_type") != "http" and "http" not in obj:
                continue
            ts = obj.get("timestamp") or obj.get("ts")
            try:
                ts_dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                ts_dt = datetime.datetime.utcnow()
            http = obj.get("http", {})
            src_ip = obj.get("src_ip") or obj.get("src_addr")
            dest_ip = obj.get("dest_ip") or obj.get("dest_addr")
            events.append({
                "ts": ts_dt,
                "src_ip": src_ip,
                "dest_ip": dest_ip,
                "method": http.get("http_method") or http.get("method"),
                "url": http.get("url") or http.get("http_host", "") + (http.get("uri", "") or ""),
                "status": int(http.get("status", 0) or 0),
                "body": http.get("body", "") or http.get("http_body", ""),
            })
    return events


def parse_attack_logs(path: str) -> List[Dict[str, Any]]:
    """Parse attack log JSON files which may be an array or JSON-lines.
    Returns list of normalized events similar to parse_suricata.
    """
    events = []
    p = Path(path)
    if not p.exists():
        return events
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                for obj in data:
                    ts = obj.get("timestamp") or obj.get("time")
                    try:
                        ts_dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        ts_dt = datetime.datetime.utcnow()
                    events.append({
                        "ts": ts_dt,
                        "src_ip": obj.get("src_ip") or obj.get("ip"),
                        "dest_ip": obj.get("dest_ip"),
                        "method": obj.get("method"),
                        "url": obj.get("url") or obj.get("path"),
                        "status": int(obj.get("status", 0) or 0),
                        "body": obj.get("payload") or obj.get("body", ""),
                    })
            else:
                fh.seek(0)
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    ts = obj.get("timestamp") or obj.get("time")
                    try:
                        ts_dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        ts_dt = datetime.datetime.utcnow()
                    events.append({
                        "ts": ts_dt,
                        "src_ip": obj.get("src_ip") or obj.get("ip"),
                        "dest_ip": obj.get("dest_ip"),
                        "method": obj.get("method"),
                        "url": obj.get("url") or obj.get("path"),
                        "status": int(obj.get("status", 0) or 0),
                        "body": obj.get("payload") or obj.get("body", ""),
                    })
    except Exception:
        return []
    return events


def extract_features(events: List[Dict[str, Any]]) -> Tuple[List[List[float]], List[Dict[str, Any]]]:
    """Given normalized events, compute feature vector per event and return (X, meta).

    Features (8):
      - request_rate: requests/min from same src_ip
      - failed_requests: failed (>=400) in last minute from src_ip
      - status_class: status//100
      - payload_length: len(body)
      - entropy: Shannon entropy of body
      - inter_arrival_time: seconds since previous request from same ip
      - unusual_endpoint: 1/0 if URL contains suspicious patterns
      - method_abuse: 1/0 if method not typical
    """
    events = sorted(events, key=lambda e: e["ts"]) if events else []
    by_ip: Dict[str, deque] = defaultdict(lambda: deque())
    X = []
    meta = []
    for ev in events:
        ip = ev.get("src_ip") or "0.0.0.0"
        now = ev.get("ts")
        window = 60
        dq = by_ip[ip]
        while dq and (now - dq[0][0]).total_seconds() > window:
            dq.popleft()
        request_rate = len(dq) / (window / 60.0) if dq else 0.0
        failed_requests = sum(1 for (t, s) in dq if (s or 0) >= 400)
        status = int(ev.get("status") or 0)
        status_class = status // 100
        body = ev.get("body") or ""
        payload_length = len(body)
        entropy = _shannon_entropy(body)
        if dq:
            inter_arrival_time = (now - dq[-1][0]).total_seconds()
        else:
            inter_arrival_time = 9999.0
        url = (ev.get("url") or "")
        suspicious_tokens = ["' OR", "--", "UNION", "<script>", "../", "%27", "select "]
        unusual_endpoint = int(any(tok.lower() in url.lower() for tok in suspicious_tokens))
        method = (ev.get("method") or "GET").upper()
        method_abuse = int(method not in TYPICAL_METHODS)

        features = [
            float(request_rate),
            float(failed_requests),
            float(status_class),
            float(payload_length),
            float(entropy),
            float(inter_arrival_time),
            float(unusual_endpoint),
            float(method_abuse),
        ]
        X.append(features)
        meta.append({"src_ip": ip, "ts": now.isoformat(), "url": url, "method": method, "status": status})
        dq.append((now, status))
    return X, meta


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract features from Suricata / attack logs")
    parser.add_argument("--suricata", help="Path to eve.json")
    parser.add_argument("--attacks", help="Path to attack logs (sql/xss)")
    parser.add_argument("--out", help="Output JSON file for features", default=None)
    args = parser.parse_args()
    all_events = []
    if args.suricata:
        all_events += parse_suricata(args.suricata)
    if args.attacks:
        all_events += parse_attack_logs(args.attacks)
    X, meta = extract_features(all_events)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"X": X, "meta": meta}, fh, default=str)
    else:
        print(json.dumps({"n_samples": len(X)}))
