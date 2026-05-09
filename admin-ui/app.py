import json
import os
import time
from functools import wraps
from pathlib import Path

import requests
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-admin-secret")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
KONG_ADMIN_URL = os.getenv("KONG_ADMIN_URL", "http://kong:8001")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:5001")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:5002")
SURICATA_CONFIG_PATH = os.getenv("SURICATA_CONFIG_PATH", "/shared/suricata.yaml")
SURICATA_EVE_PATH = os.getenv("SURICATA_EVE_PATH", "/shared/eve.json")
KONG_CACHE_TTL = int(os.getenv("KONG_CACHE_TTL", "8"))
SURICATA_ALERTS_CACHE_TTL = int(os.getenv("SURICATA_ALERTS_CACHE_TTL", "8"))

_cache_store = {}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def read_text_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        return f"Unable to read {path}: {exc}"


def cache_get(key: str):
    entry = _cache_store.get(key)
    if not entry:
        return None
    if time.time() >= entry["expires_at"]:
        _cache_store.pop(key, None)
        return None
    return entry["value"]


def cache_set(key: str, value, ttl_seconds: int):
    _cache_store[key] = {
        "value": value,
        "expires_at": time.time() + max(1, ttl_seconds),
    }
    return value


def get_kong_snapshot(force_refresh: bool = False) -> dict:
    cache_key = "kong_snapshot"
    if not force_refresh:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    snapshot = {"ok": False, "error": None, "services": [], "routes": [], "plugins": []}
    try:
        for resource in ("services", "routes", "plugins"):
            response = requests.get(f"{KONG_ADMIN_URL}/{resource}", timeout=4)
            response.raise_for_status()
            snapshot[resource] = response.json().get("data", [])
        snapshot["ok"] = True
    except Exception as exc:
        snapshot["error"] = str(exc)

    # Cache only successful snapshots to avoid persisting transient startup errors.
    if snapshot["ok"]:
        return cache_set(cache_key, snapshot, KONG_CACHE_TTL)
    return snapshot


def get_suricata_alerts(limit: int = 20, force_refresh: bool = False) -> dict:
    cache_key = f"suricata_alerts_{limit}"
    if not force_refresh:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    alerts = []
    errors = []
    path = Path(SURICATA_EVE_PATH)

    if not path.exists():
        return {"ok": False, "error": f"Missing file: {SURICATA_EVE_PATH}", "alerts": []}

    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("event_type") != "alert":
                    continue

                alert = event.get("alert", {})
                alerts.append(
                    {
                        "timestamp": event.get("timestamp"),
                        "src_ip": event.get("src_ip"),
                        "dest_ip": event.get("dest_ip"),
                        "signature": alert.get("signature"),
                        "category": alert.get("category"),
                        "severity": alert.get("severity"),
                    }
                )
    except Exception as exc:
        errors.append(str(exc))

    result = {"ok": not errors, "error": errors[0] if errors else None, "alerts": alerts[-limit:]}

    # Cache only successful parses to avoid stale error states in the UI.
    if result["ok"]:
        return cache_set(cache_key, result, SURICATA_ALERTS_CACHE_TTL)
    return result


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_authenticated"] = True
            session["admin_user"] = username
            return redirect(url_for("dashboard"))

        flash("Invalid admin credentials", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", admin_user=session.get("admin_user", "admin"))


@app.route("/api/status")
@login_required
def api_status():
    kong = get_kong_snapshot()
    alerts = get_suricata_alerts(limit=20)

    return jsonify(
        {
            "admin_user": session.get("admin_user"),
            "kong": {
                "ok": kong.get("ok", False),
                "error": kong.get("error"),
                "services_count": len(kong.get("services", [])),
                "routes_count": len(kong.get("routes", [])),
                "plugins_count": len(kong.get("plugins", [])),
            },
            "suricata": {
                "config_path": SURICATA_CONFIG_PATH,
                "eve_path": SURICATA_EVE_PATH,
                "recent_alerts_count": len(alerts.get("alerts", [])),
            },
        }
    )


@app.route("/api/kong/config")
@login_required
def api_kong_config():
    return jsonify(get_kong_snapshot())


@app.route("/api/suricata/config")
@login_required
def api_suricata_config():
    return jsonify(
        {
            "ok": True,
            "path": SURICATA_CONFIG_PATH,
            "content": read_text_file(SURICATA_CONFIG_PATH),
        }
    )


@app.route("/api/suricata/alerts")
@login_required
def api_suricata_alerts():
    return jsonify(get_suricata_alerts())


@app.route("/api/auth/login", methods=["POST"])
@login_required
def api_auth_login():
    payload = request.get_json(silent=True) or {}
    response = requests.post(
        f"{USER_SERVICE_URL}/users/login",
        json={
            "username": payload.get("username", ""),
            "password": payload.get("password", ""),
        },
        timeout=10,
    )
    return jsonify(response.json()), response.status_code


@app.route("/api/test/<service_name>", methods=["POST"])
@login_required
def api_test_service(service_name: str):
    payload = request.get_json(silent=True) or {}
    path = payload.get("path", "/")
    method = payload.get("method", "GET").upper()
    token = payload.get("token", "")
    body = payload.get("body")

    if service_name == "users":
        base_url = USER_SERVICE_URL
    elif service_name == "payments":
        base_url = PAYMENT_SERVICE_URL
    else:
        return jsonify({"error": "Unknown service"}), 400

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            json=body,
            timeout=10,
        )
        content_type = response.headers.get("Content-Type", "")
        body_data = response.json() if "application/json" in content_type else response.text
        return (
            jsonify(
                {
                    "status_code": response.status_code,
                    "service": service_name,
                    "path": path,
                    "method": method,
                    "body": body_data,
                }
            ),
            response.status_code,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
