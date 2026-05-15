"""
models.py

Implements three detectors:
 - RandomForestDetector (scikit-learn)
 - AutoencoderDetector (numpy-only PCA-like)
 - HybridDetector combining both

Each class provides `fit` and `predict_single` methods. Predictions include probability,
confidence label (LOW/MEDIUM/HIGH), is_attack boolean, and latency_ms.

Usage: imported by `anomaly_detector.py` or used standalone for quick checks.
"""
from __future__ import annotations
import time
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from typing import Tuple, Dict, Any


class RandomForestDetector:
    def __init__(self, threshold: float = 0.55):
        self.threshold = threshold
        self.model = RandomForestClassifier(n_estimators=50, random_state=0)
        self.is_trained = False

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.model.fit(X, y)
        self.is_trained = True

    def predict_single(self, x: np.ndarray) -> Dict[str, Any]:
        start = time.perf_counter()
        if not self.is_trained:
            raise RuntimeError("RF not trained")
        prob = float(self.model.predict_proba(x.reshape(1, -1))[:, 1][0])
        if prob >= 0.9:
            conf = "HIGH"
        elif prob >= 0.7:
            conf = "MEDIUM"
        else:
            conf = "LOW"
        is_attack = prob >= self.threshold
        latency_ms = (time.perf_counter() - start) * 1000.0
        return {"prob": prob, "confidence": conf, "is_attack": bool(is_attack), "latency_ms": latency_ms}


class AutoencoderDetector:
    """Lightweight PCA-based reconstructor acting as an autoencoder substitute.

    Train on normal data only. Detection via reconstruction MSE.
    """
    def __init__(self, n_components: int = 4):
        self.n_components = n_components
        self.mean = None
        self.components = None
        self.threshold = None

    def fit(self, X: np.ndarray):
        # center
        self.mean = X.mean(axis=0)
        Xc = X - self.mean
        U, S, VT = np.linalg.svd(Xc, full_matrices=False)
        self.components = VT[: self.n_components]
        # compute reconstruction errors on train set
        rec = self.reconstruct(X)
        errs = ((X - rec) ** 2).mean(axis=1)
        self.threshold = float(errs.mean() + 3 * errs.std())

    def reconstruct(self, X: np.ndarray) -> np.ndarray:
        Xc = X - self.mean
        proj = Xc @ self.components.T @ self.components
        return proj + self.mean

    def predict_single(self, x: np.ndarray) -> Dict[str, Any]:
        import time as _t
        start = _t.perf_counter()
        rec = self.reconstruct(x.reshape(1, -1))
        err = float(((x - rec[0]) ** 2).mean())
        prob = min(1.0, err / (self.threshold or (1e-6)))
        if err >= (self.threshold or 1e9):
            conf = "HIGH"
        elif err >= (self.threshold or 1e9) * 0.7:
            conf = "MEDIUM"
        else:
            conf = "LOW"
        is_attack = err >= (self.threshold or 1e9)
        latency_ms = (_t.perf_counter() - start) * 1000.0
        return {"prob": prob, "confidence": conf, "is_attack": bool(is_attack), "latency_ms": latency_ms}


class HybridDetector:
    def __init__(self, rf: RandomForestDetector, ae: AutoencoderDetector):
        self.rf = rf
        self.ae = ae

    def predict_single(self, x: np.ndarray) -> Dict[str, Any]:
        start = time.perf_counter()
        rf_res = self.rf.predict_single(x)
        ae_res = self.ae.predict_single(x)
        # combine
        rf_high = rf_res["confidence"] == "HIGH"
        ae_high = ae_res["confidence"] == "HIGH"
        decision = "ALLOW"
        if rf_res["is_attack"] and ae_res["is_attack"]:
            decision = "BLOCK_HIGH"
        elif rf_high and not ae_res["is_attack"]:
            decision = "BLOCK"
        elif ae_high and not rf_res["is_attack"]:
            decision = "BLOCK"
        elif rf_res["is_attack"] != ae_res["is_attack"]:
            decision = "MONITOR"
        else:
            decision = "ALLOW"
        latency_ms = (time.perf_counter() - start) * 1000.0
        return {
            "rf": rf_res,
            "ae": ae_res,
            "decision": decision,
            "latency_ms": latency_ms,
        }
