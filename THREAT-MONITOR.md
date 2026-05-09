# Threat Monitor: Automatic IP Blocking System

## Overview

Threat Monitor est un service automatisé qui crée une boucle de feedback entre Suricata (IDS) et Kong (API Gateway):

```
┌──────────────┐
│  Attacker    │
│  IP: 1.2.3.4 │
└──────┬───────┘
       │ (attack traffic)
       ▼
┌──────────────────────┐
│   Kong Gateway       │
│   Port 8000          │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Microservices       │
│  (user, payment)     │
└──────┬───────────────┘
       │
       ▼ (network traffic)
┌──────────────────────┐
│  Suricata (IDS)      │
│  Monitoring          │
│  Alert: IP 1.2.3.4   │
│  → eve.json          │
└──────┬───────────────┘
       │ (alerts)
       ▼
┌──────────────────────┐
│  Threat Monitor      │
│  Parsing eve.json    │
│  Detecting patterns  │
└──────┬───────────────┘
       │ (API call)
       ▼
┌──────────────────────┐
│  Kong Admin API      │
│  Port 8001           │
│  Add IP to blocklist │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  IP: 1.2.3.4         │
│  BLOCKED ❌          │
└──────────────────────┘
```

## Flow Description

1. **Suricata detects attack**: L'attaquant tente d'exploiter une vulnérabilité SQL Injection, XSS, etc.
2. **Alert generated**: Suricata génère une alerte JSON dans `eve.json`.
3. **Threat Monitor reads alerts**: Le service threat-monitor lit eve.json en continu.
4. **Threshold check**: Si une IP génère 5 alertes en 5 minutes, elle est flaggée.
5. **Kong API call**: threat-monitor ajoute l'IP malveillante via Kong Admin API.
6. **IP blocked**: Kong bloque instantanément les requêtes de cette IP.

## Components

### 1. Suricata
- **Role**: Détection d'intrusions (IDS)
- **Output**: eve.json (format JSON)
- **Alerts**: SQL injection, XSS, DoS, brute force, etc.

### 2. Threat Monitor
- **Service**: Container Python
- **Function**: Parses eve.json, agrège les alertes par IP
- **Action**: Envoie des commandes à Kong Admin API
- **Threshold**: 5 alertes / 300 secondes par IP

### 3. Kong
- **Role**: API Gateway avec enforcement
- **Plugin**: ip-restriction sur les services user-service et payment-service
- **Admin API**: Reçoit les IPs à bloquer
- **Effect**: 403 Forbidden pour les IPs bloquées

## Configuration

### Docker Compose

```yaml
threat-monitor:
  build: ../threat-monitor
  environment:
    KONG_ADMIN_URL: http://kong:8001
  volumes:
    - ./suricata/logs:/var/log/suricata:ro
  networks:
    - kong-net
```

### Kong Services (kong.yml)

```yaml
services:
  - name: user-service
    plugins:
      - name: ip-restriction
        config:
          deny: []  # Sera rempli automatiquement par threat-monitor
```

## How It Works

### Alert Aggregation

Threat monitor agrège les alertes par adresse IP source:

```json
{
  "192.168.1.100": [
    {
      "timestamp": "2026-04-24T10:30:00Z",
      "message": "SQL Injection - UNION SELECT"
    },
    {
      "timestamp": "2026-04-24T10:30:05Z",
      "message": "SQL Injection - OR 1=1"
    },
    ...
  ]
}
```

Quand la limite est atteinte (5 alertes), l'IP est envoyée à Kong.

### Kong API Call

```bash
# Example: Add IP to user-service
PATCH http://kong:8001/services/user-service/plugins/<plugin_id>
{
  "config": {
    "deny": ["192.168.1.100", "10.0.0.5", ...]
  }
}
```

### Blocked IPs Tracking

Les IPs bloquées sont sauvegardées dans `/tmp/blocked_ips.json`:

```json
{
  "192.168.1.100": {
    "blocked_at": "2026-04-24T10:30:15Z",
    "reason": "SQL Injection - detected 5 alerts in 5m"
  }
}
```

## Testing

### 1. Monitor Threat Monitor Logs

```bash
docker logs threat-monitor -f
```

### 2. Simulate Attack

```bash
# SQL injection attempt (will trigger alerts in Suricata)
curl "http://localhost:8000/users?id=1' OR '1'='1"

# Check eve.json
docker exec suricata tail -f /var/log/suricata/eve.json | grep -i sql
```

### 3. Check Blocked IPs

```bash
# View Kong plugins
curl http://localhost:8001/services/user-service/plugins

# Check blocked IPs file
docker exec threat-monitor cat /tmp/blocked_ips.json
```

### 4. Verify Blocking

```bash
# Should get 403 Forbidden after IP is blocked
curl -H "X-Forwarded-For: 192.168.1.100" http://localhost:8000/users
```

## Tuning Parameters

Edit `threat_monitor.py`:

```python
ALERT_THRESHOLD = 5       # Nombre d'alertes avant blocage
TIME_WINDOW = 300         # Fenêtre temporelle (en secondes)
KONG_ADMIN_URL = "http://kong:8001"  # URL Kong Admin API
```

### Examples

- **Blocking rapide**: `ALERT_THRESHOLD = 2, TIME_WINDOW = 60` (2 alerts / 1 min)
- **Blocking strict**: `ALERT_THRESHOLD = 1, TIME_WINDOW = 3600` (1 alert / 1 heure = permanent)
- **Blocking permissif**: `ALERT_THRESHOLD = 20, TIME_WINDOW = 3600` (20 alerts / 1 heure)

## Architecture Benefits

1. **Automated**: Pas d'intervention manuelle pour bloquer les IPs
2. **Real-time**: Les IPs sont bloquées en quelques secondes
3. **Granulated**: Bloque au niveau des services Kong, pas à l'OS
4. **Reversible**: Les IPs peuvent être débloquées manuellement via Kong API
5. **Observable**: Tous les événements sont loggés

## Limitations & Future Improvements

### Current Limitations

1. **Windows mode host**: Suricata en `network_mode: host` expose tout le PC
   - **Solution**: Déployer sur Linux serveur ou utiliser une VM isolée

2. **No whitelist**: Pas de liste blanche d'IPs de confiance
   - **À ajouter**: Whitelist dans Kong config ou threat-monitor

3. **No auto-unblock**: Les IPs restent bloquées indéfiniment
   - **À ajouter**: TTL (Time To Live) pour déblocage automatique après 24h

4. **Basic aggregation**: Seulement compte les alertes par IP
   - **À améliorer**: Pattern d'attaques spécifiques + contexte

### Future Enhancements

```python
# Whitelist support
WHITELIST_IPS = ["10.0.0.1", "192.168.0.0/24"]

# Auto-unblock with TTL (24 heures)
if (now - blocked_time).total_seconds() > 86400:
    unblock_ip(ip)

# Alert severity levels
if alert_severity in ["critical", "emergency"]:
    block_immediately()
```

## Troubleshooting

### Threat Monitor not starting

```bash
# Check logs
docker logs threat-monitor

# Check Kong connectivity
docker exec threat-monitor curl http://kong:8001/

# Check Suricata logs volume
docker exec threat-monitor ls -la /var/log/suricata/
```

### IPs not being blocked

1. Vérifie que Suricata génère des alertes:
   ```bash
   docker logs suricata | grep -i alert
   ```

2. Vérifie eve.json:
   ```bash
   docker exec suricata tail -20 /var/log/suricata/eve.json
   ```

3. Check threat-monitor parsing:
   ```bash
   docker logs threat-monitor | grep "BLOCKED"
   ```

### Kong API errors

```bash
# Verify Kong is responding
curl http://localhost:8001/services

# Check plugin status
curl http://localhost:8001/services/user-service/plugins
```

## References

- [Suricata Documentation](https://suricata.io/documentation/)
- [Kong Admin API](https://docs.konghq.com/gateway/latest/admin-api/)
- [IP Restriction Plugin](https://docs.konghq.com/hub/kong-inc/ip-restriction/)
