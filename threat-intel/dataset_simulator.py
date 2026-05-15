"""
dataset_simulator.py

Simulate a dataset (CIC-IDS2017 + CSIC2010-like) with normal and attack samples.

Usage (CLI):
    python dataset_simulator.py --out simulated.npz

Exports:
    generate_dataset() -> X (np.ndarray), y (np.ndarray), attack_types (list[str])

Designed to be importable by `anomaly_detector.py`.
"""
from __future__ import annotations
import numpy as np
from typing import Tuple, List


def _make_normal(n: int, seed: int = 42):
    rs = np.random.RandomState(seed)
    request_rate = rs.poisson(2, size=n).astype(float)
    failed = rs.poisson(0.1, size=n).astype(float)
    status = rs.choice([2.0, 3.0], size=n, p=[0.9, 0.1])
    payload = rs.normal(200, 50, size=n).clip(0)
    entropy = rs.normal(3.0, 0.5, size=n).clip(0)
    iat = rs.exponential(10, size=n)
    unusual = rs.binomial(1, 0.01, size=n)
    method_abuse = rs.binomial(1, 0.01, size=n)
    X = np.vstack([request_rate, failed, status, payload, entropy, iat, unusual, method_abuse]).T
    return X


def _make_attack(n: int, kind: str, seed: int = None):
    rs = np.random.RandomState(seed or 1)
    base = _make_normal(n, seed=seed or 1)
    X = base.copy()
    if kind == "sqli":
        X[:, 6] = 1.0
        X[:, 3] += rs.normal(50, 20, size=n)
        X[:, 4] += 2.0
    elif kind == "xss":
        X[:, 6] = 1.0
        X[:, 3] += rs.normal(80, 40, size=n)
        X[:, 4] += 2.5
    elif kind == "bruteforce":
        X[:, 0] += rs.poisson(10, size=n)
        X[:, 1] += rs.poisson(1, size=n)
        X[:, 7] = 1.0
    elif kind == "dos":
        X[:, 0] += rs.poisson(50, size=n)
        X[:, 1] += rs.poisson(5, size=n)
    elif kind == "scan":
        X[:, 0] += rs.poisson(5, size=n)
        X[:, 6] = 1.0
    else:
        X += rs.normal(0, 1, size=X.shape)
    return X


def generate_dataset(seed: int = 42):
    import numpy as _np
    normal = _make_normal(500, seed=seed)
    sqli = _make_attack(80, "sqli", seed=seed + 1)
    xss = _make_attack(60, "xss", seed=seed + 2)
    bruteforce = _make_attack(80, "bruteforce", seed=seed + 3)
    dos = _make_attack(60, "dos", seed=seed + 4)
    scan = _make_attack(40, "scan", seed=seed + 5)

    X = _np.vstack([normal, sqli, xss, bruteforce, dos, scan])
    y = _np.hstack([_np.zeros(len(normal)), _np.ones(len(sqli)), _np.ones(len(xss)), _np.ones(len(bruteforce)), _np.ones(len(dos)), _np.ones(len(scan))])
    attack_types = (["normal"] * len(normal) + ["sqli"] * len(sqli) + ["xss"] * len(xss) + ["bruteforce"] * len(bruteforce) + ["dos"] * len(dos) + ["scan"] * len(scan))
    return X.astype(float), y.astype(int), attack_types


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate simulated dataset for threat-intel")
    parser.add_argument("--out", help="Output .npz file to save dataset", default=None)
    args = parser.parse_args()
    X, y, types = generate_dataset()
    if args.out:
        import numpy as np
        np.savez_compressed(args.out, X=X, y=y, types=types)
        print(f"Saved dataset to {args.out}")
    else:
        print(f"Dataset: X={X.shape}, y={y.shape}")
