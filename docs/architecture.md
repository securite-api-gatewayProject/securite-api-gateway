# Secure API Gateway - Documentation Complète

**Auteur:** Projet Sécurité Cyber  
**Date:** Mars 2026  
**Status:** ✅ Fonctionnel & Déployable  
**Version:** 1.0

---

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture globale](#architecture-globale)
3. [Services implémentés](#services-implémentés)
4. [Base de données](#base-de-données)
5. [API Gateway (Kong)](#api-gateway-kong)
6. [Instructions de déploiement](#instructions-de-déploiement)
7. [Tests & Validation](#tests--validation)
8. [État du projet](#état-du-projet)
9. [Roadmap](#roadmap)

---

## Vue d'ensemble

**Secure API Gateway** est une infrastructure microservices containerisée conçue pour démontrer :
- Une **architecture API Gateway** avec Kong
- La gestion des **utilisateurs et paiements** via microservices Flask
- La **persistance des données** avec PostgreSQL
- Les **politiques de sécurité** (rate limiting, IP filtering)
- L'**orchestration Docker** pour un déploiement simplifié

### Objectifs
✅ Fournir un point d'entrée unique pour tous les services API  
✅ Appliquer des règles de sécurité globales (rate limiting, IP blacklist)  
✅ Isoler les services métier (users, payments) en microservices indépendants  
✅ Persister les données en PostgreSQL  
✅ Permettre un déploiement facile via Docker Compose  

---

## Architecture globale

```
┌────────────────────────────────────────────────────────────────┐
│                      CLIENT REQUESTS                           │
│              (via HTTP/HTTPS sur port 8000)                    │
└────────────────────────────┬─────────────────────────────────┘
                             │
                    HTTP 8000 │
                             │
        ┌────────────────────▼────────────────────┐
        │   KONG API GATEWAY (Port 8000)          │
        │  ┌──────────────────────────────────┐  │
        │  │ Sécurité & Routage:              │  │
        │  │ • Rate limiting (5 req/min)      │  │
        │  │ • IP restriction (blacklist)     │  │
        │  │ • Routing intelligent            │  │
        │  │ • Logging & Monitoring           │  │
        │  └──────────────────────────────────┘  │
         └──────┬──────────────────┬──────┘
           │                  │
            ┌────────▼──────┐  ┌───────▼──┐
            │ /users        │  │ /payments │
            │ /users/login  │  │ /payments/│
            │ /users/...    │  │ user/...  │
            └────────┬──────┘  └───────┬──┘
           │                  │
      ┌────────▼─────────────┐  ┌─▼─────────────────┐
      │ user-service (5001)  │  │ payment-service   │
      │ Flask Python         │  │ Flask Python      │
      │                      │  │ (5002)            │
      │ ✓ /health           │  │ ✓ /health         │
      │ ✓ GET /users        │  │ ✓ GET /payments   │
      │ ✓ POST /users/login │  │ ✓ POST /payments  │
      │ ✓ POST /users/reg   │  │ ✓ Filtrage status │
      └────────┬────────────┘  └─────┬──────────────┘
               │                      │
               └──────────┬───────────┘
                          │
               ┌──────────▼──────────┐
               │  PostgreSQL (5432)  │
               │                     │
               │ [api_gateway]       │
               │ ├─ users table      │
               │ └─ payments table    │
               └─────────────────────┘
```

### Composants

| Composant | Technologie | Port | Rôle |
|-----------|-------------|------|-----|
| **Kong Gateway** | API Gateway | 8000 (proxy), 8001 (admin) | Routage centralisé + sécurité |
| **user-service** | Flask + SQLAlchemy | 5001 | Gestion utilisateurs |
| **payment-service** | Flask + SQLAlchemy | 5002 | Gestion paiements |
| **PostgreSQL** | Database | 5432 | Persistance données |
| **mock-service** | Nginx | 80 (interne) | Service de test (mode test uniquement) |

---

## Services implémentés

### 1️⃣ User Service (Port 5001)

**Fichier:** `microservices/user-service/user-service.py`

**Responsabilités:**
- Authentification utilisateurs
- Créer/consulter des comptes
- Gestion des rôles (admin, user)

**Endpoints:**

```
GET  /health
     → Statut du service
     Response: { "status": "healthy", "service": "user-service", "timestamp": "2026-03-14T..." }

GET  /users
     → Liste tous les utilisateurs
     Response: { "users": [...], "count": 3 }

GET  /users/<user_id>
     → Détail d'un utilisateur
     Response: { "id": "1", "username": "alice", "email": "alice@example.com", ... }

POST /users/login
     → Authentifier un utilisateur
     Request:  { "username": "alice", "password": "password123" }
     Response: { "message": "Login successful", "token": "uuid-...", "user": {...} }

POST /users/register
     → Créer un nouveau compte
     Request:  { "username": "newuser", "email": "new@example.com", "password": "..." }
     Response: { "message": "User created successfully", "user": {...} }
```

**Modèle de données (User):**
```python
class User:
    id (UUID)                    # Identifiant unique
    username (string, unique)    # Pseudo unique
    email (string, unique)       # Email unique
    password_hash (SHA256)       # Mot de passe hashé
    role (admin | user)          # Type de compte
    created_at (DateTime)        # Date de création
```

**Données initiales (seed):**
```
1. alice   | alice@example.com   | password123  | admin
2. bob     | bob@example.com     | secret456    | user
3. charlie | charlie@example.com | mypassword   | user
```

**Sécurité:**
- ✅ Mots de passe en SHA256 (non réversible)
- ✅ `password_hash` masqué dans les réponses JSON
- ✅ Tokens UUIDs aléatoires au login
- ✅ Validations sur username/email/password requis
- ✅ Détection de username en doublon

**Stack technique:**
- Flask 2.3.3
- SQLAlchemy 2.0.21
- psycopg2 (PostgreSQL driver)

---

### 2️⃣ Payment Service (Port 5002)

**Fichier:** `microservices/payment-service/payment-service.py`

**Responsabilités:**
- Créer/consulter des transactions
- Gérer les statuts de paiement
- Filtrer par devise, méthode, utilisateur

**Endpoints:**

```
GET  /health
     → Statut du service

GET  /payments
     → Liste tous les paiements
     Query params: ?status=completed / ?status=pending / ?status=failed
     Response: { "payments": [...], "count": 3 }

GET  /payments/<payment_id>
     → Détail d'un paiement
     Response: { "id": "pay_001", "user_id": "1", "amount": 150.0, ... }

POST /payments
     → Créer un nouveau paiement
     Request:  {
                 "user_id": "1",
                 "amount": 99.99,
                 "currency": "EUR",
                 "method": "credit_card",
                 "description": "Achat"
               }
     Response: { "message": "Payment completed", "payment": {...} }
     Status:   201 si succès, 402 si échec

GET  /payments/user/<user_id>
     → Tous les paiements d'un utilisateur + total complétés
     Response: { "user_id": "1", "payments": [...], "count": 3, "total_completed": 350.00 }
```

**Modèle de données (Payment):**
```python
class Payment:
    id (String)                    # Identifiant unique
    user_id (String)               # Lien vers utilisateur
    amount (Float)                 # Montant
    currency (EUR|USD|GBP|MAD)    # Devise
    status (pending|completed|failed)  # État
    method (credit_card|paypal|bank_transfer|crypto)  # Mode
    description (String)           # Description
    created_at (DateTime)          # Date création
```

**Données initiales (seed):**
```
pay_001: user_id=1, amount=150€, method=credit_card, status=completed
pay_002: user_id=2, amount=49.99€, method=paypal, status=completed
pay_003: user_id=1, amount=200$, method=bank_transfer, status=pending
```

**Logique métier:**
- Validation: montant > 0, devise connue, méthode connue
- Simulation: 90% succès / 10% échecs (aléatoire)
- HTTP 201 si succès, HTTP 402 si échec
- Calcul du total des paiements complétés par utilisateur

**Stack technique:**
- Flask 2.3.3
- SQLAlchemy 2.0.21
- psycopg2

---

### 3️⃣ Base de données (PostgreSQL)

**Image:** `postgres:15-alpine` (38 MB)  
**Port:** 5432  
**Credentials:**
```
User:     postgres
Password: password
Database: api_gateway
```

**Tables:**

#### Table `users`
```sql
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
```

#### Table `payments`
```sql
CREATE TABLE payments (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    amount FLOAT NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',
    status VARCHAR(20) DEFAULT 'pending',
    method VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payments_user_id ON payments(user_id);
```

**Persistance:**
```yaml
Volume: postgres-data
Location: /var/lib/postgresql/data
Persistence: ✅ Survive redémarrages
Reset: docker-compose down -v (supprime données)
```

**Health Check:**
```
Test: pg_isready -U postgres
Interval: 10 secondes
Timeout: 5 secondes
Retries: 5
```

---

### 4️⃣ API Gateway (Kong)

**Image:** `kong:latest`  
**Ports:** 8000 (proxy) & 8001 (admin)  
**Mode:** Déclaratif (KONG_DATABASE=off)  
**Config:** `/kong/kong.yml` (monté en volume)

**Configuration Kong:**

```yaml
_format_version: "3.0"
_transform: true

services:
  - name: user-service
    host: user-service
    port: 5001
    routes:
      - paths: [/users, /users/login, /users/register]

  - name: payment-service
    host: payment-service
    port: 5002
    routes:
      - paths: [/payments, /payments/user]
```

Configuration de test (fichier `kong.test.yml`) ajoute en plus:

```yaml
services:
  - name: mock-service
    host: mock-service
    port: 80
    routes:
      - paths: [/mock]
```

**Plugins activés:**

| Plugin | Config | Effet |
|--------|--------|-------|
| **rate-limiting** | 5 req/minute | Limite 5 requêtes par minute par IP |
| **ip-restriction** | deny: 1.2.3.4 | Bloque IP 1.2.3.4 (test) |
| **request-termination** | (commenté) | Peut retourner 403 Access Denied |

**Fonctionnement:**
1. Client envoie requête à `http://localhost:8000/users`
2. Kong vérifie rate-limiting (OK si < 5 req/min)
3. Kong vérifie IP (OK si pas de blacklist)
4. Kong route vers `http://user-service:5001/users`
5. user-service répond
6. Kong retourne la réponse au client

**Logging:**
```
KONG_PROXY_ACCESS_LOG: /dev/stdout       # Logs des requêtes
KONG_PROXY_ERROR_LOG: /dev/stderr        # Logs des erreurs
```

Visible avec: `docker-compose logs -f kong`

---

## Instructions de déploiement

### Prérequis

- Docker Desktop (ou Docker + Docker Compose)
- PowerShell / Terminal
- 2 GB de RAM libre (minimum)

### Démarrage complet

```powershell
# 1. Naviguer vers le dossier infra
cd securite-api-gateway/infra

# 2. Lancer Docker Compose (build + run)
docker-compose up --build

# 3. Attendre le message "services are running"
# ~ 30-60 secondes
```

**Chronologie de démarrage:**
```
t=0s  : PostgreSQL démarre
t=5s  : PostgreSQL ready (health check OK)
t=6s  : user-service build + start (crée tables, insère users)
t=7s  : payment-service build + start (crée tables, insère payments)
t=8s  : Kong start + charge kong.yml
t=9s  : Kong prêt
t=10s : ✅ Système complet fonctionnel
```

### Arrêt

```powershell
# Arrêt simple (conteneurs conservent état)
docker-compose down

# Arrêt complet + reset données
docker-compose down -v

# Arrêt + delete images
docker-compose down --rmi all
```

### Commandes utiles

```powershell
# Voir les logs en temps réel
docker-compose logs -f

# Voir logs d'un service spécifique
docker-compose logs -f kong
docker-compose logs -f user-service

# Lister les conteneurs
docker-compose ps

# Exécuter une commande dans un conteneur
docker-compose exec postgres psql -U postgres -d api_gateway

# Redémarrer un service
docker-compose restart user-service
```

---

## Tests & Validation

### Test 1: Direct aux microservices

```bash
# User Service direct
curl http://localhost:5001/users
# Response: { "users": [...], "count": 3 }

# Payment Service direct
curl http://localhost:5002/payments
# Response: { "payments": [...], "count": 3 }
```

✅ **Attendu:** Données retournées directement sans passer par Kong

### Test 2: Via Kong Gateway

```bash
# Requête via Kong
curl http://localhost:8000/users
# Response: { "users": [...], "count": 3 }

# Requête payments via Kong
curl http://localhost:8000/payments
# Response: { "payments": [...], "count": 3 }
```

✅ **Attendu:** Données retournées avec routage Kong

### Test 3: Rate Limiting

```bash
# Faire 6+ requêtes rapidement
for i in {1..10}; do curl http://localhost:8000/users; done

# Résultat:
# Les 5 premières → 200 OK
# À partir de la 6e → 429 Too Many Requests
```

✅ **Attendu:** Limitation des requêtes (5/min)

### Test 4: Login

```bash
# Request
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"password123"}'

# Response
{
  "message": "Login successful",
  "token": "550e8400-e29b-41d4-a716-446655440000",
  "user": {
    "id": "1",
    "username": "alice",
    "email": "alice@example.com",
    "role": "admin"
  }
}
```

✅ **Attendu:** Token généré, utilisateur authentifié

### Test 5: Création de paiement

```bash
# Request
curl -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1",
    "amount": 99.99,
    "currency": "EUR",
    "method": "credit_card",
    "description": "Test payment"
  }'

# Response
{
  "message": "Payment completed",
  "payment": {
    "id": "pay_abc123",
    "user_id": "1",
    "amount": 99.99,
    "currency": "EUR",
    "status": "completed",
    "method": "credit_card",
    "description": "Test payment",
    "created_at": "2026-03-14T14:55:00"
  }
}
```

✅ **Attendu:** Paiement créé avec succès

---

## État du projet

### ✅ Implémenté (100%)

| Composant | Status | Détail |
|-----------|--------|--------|
| PostgreSQL | ✅ | Base de données persistante, tables, data seed |
| user-service | ✅ | 5 endpoints, authentification, CRUD |
| payment-service | ✅ | 5 endpoints, CRUD, filtrage, calculs |
| Kong Gateway | ✅ | Routage, rate-limiting, IP restriction |
| Docker Compose | ✅ | Orchestration, health checks, volumes |
| Dockerfile | ✅ | Images pour user-service et payment-service |

### ⚠️ Partiellement implémenté (50%)

| Composant | Status | Détail |
|-----------|--------|--------|
| Sécurité | ⚠️ | Rate-limiting ✅, IP blacklist ✅, JWT ❌, HTTPS ❌, Audit ❌ |
| Documentation | ⚠️ | Architecture ✅, Tests ✅, Code comments ⚠️ |

### ❌ Non implémenté (0%)

| Composant | Status | Détail |
|-----------|--------|--------|
| attacks/ | ❌ | SQLi tests vide, XSS tests vide |
| threat-intel/ | ❌ | anomaly_detector vide, ip_blocker vide |
| Tests unitaires | ❌ | Aucun test pytest |
| API Keys | ❌ | Aucune authentification API |
| JWT | ❌ | Tokens UUID à la place de JWT |

### Résumé

```
Infrastructure:  ████████░░ 80% complet
Microservices:   ██████████ 100% complet
Sécurité:        ████░░░░░░ 40% complet
Documentation:   ██████░░░░ 60% complet
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL:           ███████░░░ 70% complet ✅ Fonctionnel
```

---

## Roadmap

### Phase 2 : Sécurité avancée

- [ ] Implémenter JWT (JSON Web Tokens) au lieu de UUID
- [ ] Ajouter HTTPS/TLS (certificats auto-signés)
- [ ] Ajouter OAuth2 / OpenID Connect
- [ ] Audit logging (qui a accédé à quoi, quand)
- [ ] Rate limiting par utilisateur (pas juste par IP)

### Phase 3 : Threat Intelligence

- [ ] Implémenter `anomaly_detector.py` (détection comportements suspects)
- [ ] Implémenter `ip_blocker.py` (bloquer IPs dynamiquement)
- [ ] Integration avec logs Kong
- [ ] Alertes en temps réel

### Phase 4 : Tests Offensifs

- [ ] Implémenter `sql_injection.py` (tester vulnérabilités SQLi)
- [ ] Implémenter `xss_attack.py` (tester vulnérabilités XSS)
- [ ] Ajouter tests de fuzzing
- [ ] Ajouter tests penetration

### Phase 5 : Scaling & Monitoring

- [ ] Prometheus metrics + Grafana dashboard
- [ ] ELK Stack (Elasticsearch + Logstash + Kibana)
- [ ] Kubernetes deployment (au lieu de Docker Compose)
- [ ] Load testing (Apache JMeter / Locust)
- [ ] CI/CD pipeline (GitHub Actions)

---

## Structure des fichiers

```
securite-api-gateway/
├── 📄 README.md                           [À créer]
├── 📂 infra/
│   ├── docker-compose.yml                 [Orchestration]
│   └── kong.yml                           [Config Kong]
│
├── 📂 microservices/
│   ├── 📂 user-service/
│   │   ├── user-service.py                [Service Flask]
│   │   ├── Dockerfile                     [Build image]
│   │   └── requirements.txt               [Dépendances]
│   │
│   └── 📂 payment-service/
│       ├── payment-service.py             [Service Flask]
│       ├── Dockerfile                     [Build image]
│       └── requirements.txt               [Dépendances]
│
├── 📂 attacks/
│   ├── sql_injection.py                   [À implémenter]
│   └── xss_attack.py                      [À implémenter]
│
├── 📂 threat-intel/
│   ├── anomaly_detector.py                [À implémenter]
│   └── ip_blocker.py                      [À implémenter]
│
└── 📂 docs/
    └── architecture.md                    [Cette page]
```

---

## Dépendances

### Python (Flask services)
```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
SQLAlchemy==2.0.21
psycopg2-binary==2.9.7
python-dotenv==1.0.0
```

### Docker Images
```
postgres:15-alpine        (38 MB, base de données)
kong:latest              (300+ MB, API Gateway)
nginx:latest             (40 MB, mock-service en mode test)
python:3.11-slim         (130 MB, user-service, payment-service)
```

### Total
- ~500 MB sans données
- ~2 GB avec données

---

## Troubleshooting

### Kong retourne 404

**Problème:** Routes non reconnues  
**Solution:** 
1. Vérifier kong.yml syntaxe YAML
2. Redémarrer Kong: `docker-compose restart kong`
3. Vérifier logs: `docker-compose logs kong`

### PostgreSQL ne démarre pas

**Problème:** Erreur de connexion  
**Solution:**
1. Vérifier port 5432 libre: `netstat -ano | findstr 5432`
2. Réinitialiser: `docker-compose down -v`
3. Relancer: `docker-compose up --build`

### Microservices ne répondent pas

**Problème:** Timeout connexion DB  
**Solution:**
1. Vérifier PostgreSQL est UP: `docker-compose logs postgres`
2. Vérifier DATABASE_URL correcte
3. Redémarrer services: `docker-compose restart user-service payment-service`

### Ports déjà utilisés

**Problème:** Address already in use  
**Solution:**
```powershell
# Tuer le processus sur le port
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Ou utiliser docker-compose complete reset
docker-compose down
docker system prune -f
```

---

## Conclusion

**Secure API Gateway** est une infrastructure **production-ready** (MiniProd) qui démontre :

✅ **Microservices architecture** avec services indépendants  
✅ **API Gateway pattern** avec Kong  
✅ **Containerization** avec Docker  
✅ **Database persistence** avec PostgreSQL  
✅ **Security policies** (rate limiting, IP filtering)  
✅ **Easy deployment** via Docker Compose  

Le projet est **extensible** et prêt pour ajouter :
- Sécurité avancée (JWT, OAuth2)
- Tests offensifs (SQLi, XSS)
- Threat intelligence
- Monitoring & observabilité

---

**Dernière mise à jour:** 14 Mars 2026  
**License:** Educational Purpose  
**Contact:** Projet Cyber Senestre 2
