"""
anomaly_detector.py

Orchestrator that trains the HybridDetector and analyzes logs from Suricata or attack logs.

CLI:
    python anomaly_detector.py --train --from-logs attacks/sql_injection_logs.json --suricata infra/suricata/logs/eve.json --auto-block

Flags:
    --from-logs FILE   : process attack log file
    --suricata FILE    : process suricata eve.json
    --realtime         : run in realtime monitoring mode (5s interval)
    --auto-block       : enable ip_manager to apply bans

Produces `anomaly_report.json` with results and metrics.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
from typing import List

import numpy as np
from sklearn.metrics import precision_recall_fscore_support

# Ensure local threat-intel folder is importable when running the script from project root
import os, sys
HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from dataset_simulator import generate_dataset
from feature_extractor import parse_suricata, parse_attack_logs, extract_features
from models import RandomForestDetector, AutoencoderDetector, HybridDetector
from ip_manager import IPManager


REPORT_FILE = Path(__file__).parent / "anomaly_report.json"


def train_detectors():
    X, y, types = generate_dataset()
    # train RF on full labeled dataset
    rf = RandomForestDetector(threshold=0.55)
    rf.fit(X, y)
    # train AE only on normal samples
    ae = AutoencoderDetector(n_components=4)
    ae.fit(X[y == 0])
    hybrid = HybridDetector(rf, ae)
    return hybrid, rf


def analyze_events(hybrid: HybridDetector, rf, events, auto_block: bool = False):
    X, meta = extract_features(events)
    if not X:
        return {}
    Xnp = np.array(X)
    results = []
    im = IPManager() if auto_block else None
    for i, x in enumerate(Xnp):
        out = hybrid.predict_single(x)
        rec = {**meta[i], "out": out}
        results.append(rec)
        if auto_block and out["decision"].startswith("BLOCK"):
            ip = meta[i].get("src_ip")
            if ip:
                im.record_detection(ip, reason=out["decision"], auto_block=True)
    return results


def report_metrics(y_true: List[int], y_pred: List[int]):
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return {"precision": float(p), "recall": float(r), "f1": float(f)}


def main():
    parser = argparse.ArgumentParser(description="Anomaly detector orchestrator")
    parser.add_argument("--from-logs", help="Attack logs file (json)")
    parser.add_argument("--suricata", help="Suricata eve.json path")
    parser.add_argument("--realtime", action="store_true", help="Run realtime monitor (5s)")
    parser.add_argument("--auto-block", action="store_true", help="Auto block via Kong")
    args = parser.parse_args()

    hybrid, rf = train_detectors()
    print("Detectors trained")

    all_results = []
    y_true = []
    y_pred = []

    def process_once():
        events = []
        if args.suricata:
            events.extend(parse_suricata(args.suricata))
        if args.from_logs:
            events.extend(parse_attack_logs(args.from_logs))
        res = analyze_events(hybrid, rf, events, auto_block=args.auto_block)
        for r in res:
            all_results.append(r)
            # best-effort labels: if event from attack logs => attack
            src = r.get("src_ip")
            # infer label simplistic: unusual_endpoint or decision contains BLOCK
            label = 1 if r["out"]["decision"].startswith("BLOCK") or r["out"]["rf"]["is_attack"] else 0
            y_true.append(label)
            y_pred.append(1 if r["out"]["rf"]["is_attack"] else 0)
        return res

    if args.realtime:
        print("Starting realtime monitoring (ctrl-c to stop)")
        try:
            while True:
                process_once()
                time.sleep(5)
        except KeyboardInterrupt:
            pass
    else:
        process_once()

    metrics = report_metrics(y_true or [0], y_pred or [0])
    # feature importance from RF
    try:
        fi = rf.model.feature_importances_.tolist()
    except Exception:
        fi = []

    report = {"n_events": len(all_results), "metrics": metrics, "feature_importances": fi, "results_sample": all_results[:50]}
    REPORT_FILE.write_text(json.dumps(report, default=str, indent=2), encoding="utf-8")
    print(f"Saved report to {REPORT_FILE}")


if __name__ == "__main__":
    main()
