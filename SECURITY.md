# 🔒 Description de la Sécurité du Système - Secure API Gateway

## Vue d'ensemble

Le système **Secure API Gateway** est une infrastructure microservices containerisée conçue avec plusieurs couches de sécurité pour protéger les données et les services contre les attaques courantes.

---

## 1. Architecture de Sécurité

### 1.1 Modèle de Défense en Profondeur

```
┌─────────────────────────────────────────────────────────────────┐
│                    COUCHE 1: INTERNET                           │
│                   (Clients externes)                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ╔════════════════▼════════════════╗
        ║  COUCHE 2: API GATEWAY (Kong)   ║
        ║  ✓ Rate Limiting                ║
        ║  ✓ IP Restriction               ║
        ║  ✓ Routing sécurisé             ║
        ║  ✓ Logging & Monitoring         ║
        ╚════════════════╤════════════════╝
                         │
        ┌────────────────┼────────────────┐
        │                │                │
    ╔═══▼════╗      ╔═══▼═════╗    ╔════▼════╗
    ║ Couche 3│      ║ Couche 3│    ║ Couche 3║
    ║ User    ║      ║ Payment ║    ║  Mock   ║
    ║ Service ║      ║ Service ║    ║ Service ║
    ║ Flask   ║      ║ Flask   ║    ║ Nginx   ║
    ╚═══╤════╝      ╚═══╤═════╝    ╚════╧════╝
        │                │
        └────────────────┤
                    ╔════▼════════╗
                    ║  Couche 4:   ║
                    ║  PostgreSQL  ║
                    ║  (Données)   ║
                    ╚══════════════╝

    ╔═══════════════════════════════════════╗
    ║  COUCHE 6: SURICATA (IDS/IPS)        ║
    ║  ✓ Détection d'intrusions             ║
    ║  ✓ Analyse du trafic réseau           ║
    ║  ✓ 80+ Règles de sécurité             ║
    ║  ✓ Logs JSON pour SIEM                ║
    ╚═══════════════════════════════════════╝
```

---

## 2. Couches de Sécurité Implémentées

### 🛡️ Couche 1: API Gateway (Kong) - Point d'entrée unique

**Localisation:** Port 8000  
**Rôle:** Filtrage, validation et routage centralisé de toutes les requêtes

#### 2.1.1 Rate Limiting (Limitation de débit)
- **Configuration:** 5 requêtes par minute (par route)
- **Policy:** Local (sans persistance)
- **Objectif:** Prévenir les attaques par force brute et DoS
- **Implémentation:**
  ```yaml
  plugins:
    - name: rate-limiting
      config:
        minute: 5
        policy: local
  ```

**Exemples d'attaques bloquées:**
- Tentatives de brute force sur les endpoints d'authentification
- Scraping massif de données
- Attaques par saturation (DoS)

#### 2.1.2 IP Restriction (Filtrage d'adresses IP)
- **Type:** Blacklist
- **Configuration actuelle:** IP `1.2.3.4` bloquée
- **Objectif:** Bloquer les adresses IP malveillantes connues
- **Implémentation:**
  ```yaml
  plugins:
    - name: ip-restriction
      config:
        deny:
          - "1.2.3.4"
  ```

#### 2.1.3 Routage Sécurisé
- Routing centralisé vers les services backend
- Isolation des services (pas d'accès direct)
- Routes configurées:
  - `/users` → user-service:5001
  - `/payments` → payment-service:5002
- Route de test optionnelle (mode test uniquement):
  - `/mock` → mock-service:80

#### 2.1.4 Logging & Monitoring
- Tous les proxies (requêtes/réponses) sont loggés
- Sortie vers stdout/stderr pour monitoring
- Access logs et error logs séparés pour analyse

---

### 🛡️ Couche 2: Authentification et Gestion des Utilisateurs

**Service:** user-service (Port 5001)  
**Framework:** Flask + SQLAlchemy

#### 2.2.1 Hachage des Mots de Passe
- **Algorithm:** SHA256
- **Implémentation:**
  ```python
  password_hash = hashlib.sha256("password123".encode()).hexdigest()
  ```
- **Avantage:** Pas de stockage en clair des mots de passe
- **Faiblesse:** SHA256 seul n'est pas idéal pour les mots de passe (à améliorer avec bcrypt/argon2)

#### 2.2.2 Endpoints d'Authentification
- `POST /users/login` - Authentification utilisateur
- `POST /users/register` - Enregistrement nouveau utilisateur
- `GET /users/<id>` - Récupération profil utilisateur
- Validation des credentials avant accès

#### 2.2.3 Modèle de Données Utilisateur
```python
class User:
    id (UUID)
    username (unique, indexed)
    email (unique)
    password_hash
    role (admin/user)
    created_at (timestamp)
```

**Sécurité des données:**
- Index sur `username` pour requêtes rapides
- ID unique (UUID) pour éviter les énumérations
- Rôles RBAC (Role-Based Access Control) pour gestion des permissions

#### 2.2.4 Séparation des Données
- Endpoint `/to_dict()` avec contrôle `include_password`
- Les mots de passe ne sont jamais retournés dans les réponses API

---

### 🛡️ Couche 3: Gestion des Paiements (Payment Service)

**Service:** payment-service (Port 5002)  
**Criticité:** Haute (données financières)

#### 2.3.1 Validation des Données
- **Méthodes de paiement acceptées:** `credit_card`, `paypal`, `bank_transfer`, `crypto`
- **Devises acceptées:** `EUR`, `USD`, `GBP`, `MAD`
- Validation stricte avant insertion en base

#### 2.3.2 Statuts de Paiement
- `pending` - En attente
- `completed` - Complété
- `failed` - Échoué

#### 2.3.3 Endpoints Sécurisés
- `GET /payments` - Liste des paiements (nécessite authentification)
- `GET /payments/<id>` - Détail d'un paiement (vérification propriétaire)
- `POST /payments` - Création paiement (validation complète)
- `GET /payments/user/<user_id>` - Paiements d'un utilisateur

#### 2.3.4 Isolation des Données
- Index sur `user_id` pour requêtes rapides
- UUID pour chaque paiement (`pay_001`, etc.)
- Timestamps pour traçabilité

---

### 🛡️ Couche 4: Base de Données (PostgreSQL)

**Port:** 5432  
**Image:** postgres:15-alpine (léger et sécurisé)

#### 2.4.1 Configuration de Sécurité
```yaml
POSTGRES_USER: postgres
POSTGRES_PASSWORD: password
POSTGRES_DB: api_gateway
```

#### 2.4.2 Persistance Volumée
```yaml
volumes:
  - postgres-data:/var/lib/postgresql/data
```
- Données persistées dans un volume Docker
- Survit aux redémarrages des conteneurs

#### 2.4.3 Health Check
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres"]
  interval: 10s
  timeout: 5s
  retries: 5
```
- Vérification that de la disponibilité de la BD
- Orchestration des dépendances (user-service et payment-service attendent la disponibilité)

#### 2.4.4 Isolation Réseau
- PostgreSQL n'est accessible que via le réseau Docker interne `kong-net`
- Port 5432 exposé mais uniquement aux conteneurs autorisés
- Accès sécurisé via variables d'environnement

---

### 🛡️ Couche 5: Isolation des Conteneurs (Docker)

#### 2.5.1 Architecture Multi-conteneur
```
├── kong (API Gateway)
├── user-service (Flask)
├── payment-service (Flask)
├── postgres (Base de données)
└── suricata (IDS/Détection d'intrusions)
```

En mode test, un conteneur supplémentaire peut être activé:
```
└── mock-service (Nginx, route /mock)
```

#### 2.5.2 Réseau Docker Isolé
- Réseau personnalisé: `kong-net`
- Les conteneurs ne peuvent communiquer que via ce réseau
- Pas d'exposition directe des services internes
- Kong est le seul point d'entrée public

#### 2.5.3 Dépendances et Orchestration
```yaml
depends_on:
  postgres:
    condition: service_healthy
```
- Les services attendent que PostgreSQL soit sain
- Prevent les connexions échouées

#### 2.5.4 Isolation des Volumes
- Les services ont accès aux volumes source (développement)
- Données applicatives isolées par service
- Pas de montage du répertoire root

---

### 🛡️ Couche 6: Détection d'Intrusions (Suricata - IDS/IPS)

#### 2.6.1 Vue d'ensemble
**Service:** Suricata (Image: jasonish/suricata:latest)  
**Rôle:** Système de Détection/Prévention d'Intrusions (IDS/IPS)  
**Port de capture:** `docker0` (interface réseau Docker)  
**Logs:** `/var/log/suricata/` avec sortie JSON pour monitoring

#### 2.6.2 Configuration
```yaml
# suricata/suricata.yaml
var:
  EXTERNAL_NET: "any"
  HTTP_PORTS: "80,81,8000,8080,8888,9080"

stream:
  reassembly:
    memcap: 256mb
    depth: 3mb

af-packet:
  - interface: docker0
    threads: auto
    cluster-type: cluster_flow
```

#### 2.6.3 Catégories de Détection
**1. Attaques d'Injection (SID 1000-1999)**
- SQL Injection (UNION SELECT, OR 1=1, DROP TABLE, EXEC)
- Détection de patterns dangereux en URI

**2. Cross-Site Scripting (XSS) (SID 2000-2999)**
- Tags `<script>`, javascript handlers
- SVG avec `onload`, IMG avec `onerror`

**3. Attaques DoS/DDoS (SID 3000-3999)**
- Détection de requêtes excessives (100+ req/60s par IP)
- Slowloris detection
- SYN Flood detection (200+ SYN/60s)

**4. Brute Force & Authentification (SID 4000-4999)**
- Tentatives multiples sur `/users/login` (10+ en 60s)
- Accès sans Authorization header

**5. Anomalies sur APIs de Paiement (SID 5000-5999)**
- Montants suspects (10+ chiffres)
- Devises invalides (non EUR/USD/GBP/MAD)

**6. Reconnaissance & Anomalies (SID 6000-6999)**
- User-Agents malveillants (sqlmap, nikto, nessus)
- Méthodes HTTP suspectes (OPTIONS, TRACE)

**7. Fuites d'Information (SID 7000-7999)**
- Erreurs PostgreSQL exposées
- Stack traces Flask
- Disclosure de ports/services

**8. Monitoring des Services (SID 8000-8999)**
- Requêtes vers Kong:8000
- Accès aux services d'authentification:5001
- Accès aux services de paiement:5002

**9. Conformité & Alertes (SID 9000-9999)**
- Payloads volumineux POST
- Scans de pages (20+ 404 en 60s)

#### 2.6.4 Format de Sortie
Logs JSON dans `/var/log/suricata/eve.json`:
```json
{
  "timestamp": "2026-04-02T10:30:45.123456+0000",
  "flow_id": 1234567890,
  "event_type": "alert",
  "alert": {
    "action": "allowed/blocked",
    "gid": 1,
    "signature_id": 1001,
    "signature": "SQL Injection - UNION SELECT",
    "category": "Web Application Attack",
    "severity": 3
  },
  "http": {
    "hostname": "localhost",
    "url": "/users?id=1' UNION SELECT--",
    "http_method": "GET"
  },
  "src_ip": "127.0.0.1",
  "dest_ip": "172.21.0.2"
}
```

#### 2.6.5 Orchestration Docker
```yaml
suricata:
  image: jasonish/suricata:latest
  command: -c /etc/suricata/suricata.yaml -i docker0
  volumes:
    - ./suricata/suricata.yaml:/etc/suricata/suricata.yaml:ro
    - ./suricata/rules:/var/lib/suricata/rules:ro
    - ./suricata/logs:/var/log/suricata
  depends_on:
    kong:
      condition: service_started
  healthcheck:
    test: ["CMD", "pgrep", "-f", "suricata"]
    interval: 30s
    timeout: 10s
    retries: 3
  restart: on-failure
```

#### 2.6.6 Points Forts de cette Implémentation
✅ Capture en mode passif (pas d'impact sur le trafic)  
✅ 80+ règles couvrant les attaques courantes  
✅ Logs JSON structurés pour intégration SIEM  
✅ Configuration modulaire et extensible  
✅ Healthcheck intégré avec restart automatique  
✅ Isolation réseau avec mounting des règles en RO

---

## 3. Menaces Protégées

### ✅ Attaques Prévenues

| Menace | Mécanisme de Protection | Couche |
|--------|------------------------|--------|
| **Brute Force** | Rate limiting (5 req/min) | Kong |
| **DoS (Denial of Service)** | Rate limiting + IP restriction | Kong |
| **IP Spoofing** | IP blacklist | Kong |
| **Injection SQL** | SQLAlchemy ORM (parameterized queries) + Suricata IDS | App + Suricata |
| **Mots de passe en clair** | Hachage SHA256 | App |
| **Accès direct aux services** | Isolation réseau Docker | Docker |
| **Données sensibles exposées** | Contrôle d'output dans to_dict() | App |
| **Connexion BD non-sécurisée** | Chaîne de connexion via variables env | App |
| **Reconnaissance d'attaquant** | Détection User-Agent suspect | Suricata |
| **Fuite d'informations** | Détection d'erreurs système exposées | Suricata |
| **Attaques XSS** | Détection de payloads XSS | Suricata |
| **Scans de vulnérabilités** | Détection de méthodes HTTP anormales | Suricata |

---

## 4. Modules de Détection Avancés

### 4.1 Anomaly Detector
**Localisation:** `threat-intel/anomaly_detector.py`  
**Statut:** ⏳ À implémenter

**Objectif prévu:**
- Détection en temps réel d'anomalies
- Machine Learning sur les patterns d'accès
- Alertes pour comportements suspects

### 4.2 IP Blocker
**Localisation:** `threat-intel/ip_blocker.py`  
**Statut:** ⏳ À implémenter

**Objectif prévu:**
- Enrichissement des blacklists en temps réel
- Intelligence sur les menaces
- Auto-blocking des IPs malveillantes

---

## 5. Vulnérabilités Connues & Recommandations

### ⚠️ Problèmes de Sécurité Actuels

#### 5.1 Hachage des Mots de Passe Faible
```python
# ❌ Actuel (SHA256 simple)
password_hash = hashlib.sha256("password123".encode()).hexdigest()

# ✅ Recommandé (Argon2)
from argon2 import PasswordHasher
ph = PasswordHasher()
password_hash = ph.hash("password123")
```
**Risque:** Vulnérable aux attaques par table arc-en-ciel  
**Impact:** Haut (explosion de mots de passe)

#### 5.2 Credentials en Clair dans docker-compose.yml
```yaml
# ❌ Actuel
POSTGRES_PASSWORD: password

# ✅ Recommandé
POSTGRES_PASSWORD: ${DB_PASSWORD}  # via .env
```
**Risque:** Exposition des credentials en contrôle de version  
**Impact:** Critique

#### 5.3 Pas d'HTTPS/TLS
- ❌ Connexions en HTTP simple
- ✅ À mettre en HTTPS en production

#### 5.4 Rate Limiting Faible
- ❌ 5 req/min peut être insuffisant pour les APIs légitimes
- ✅ Adapter selon les besoins réels

#### 5.5 Modules de Détection Incomplets
- ❌ `anomaly_detector.py` et `ip_blocker.py` sont vides
- ✅ À implémenter

---

## 6. Recommandations de Sécurité

### 🔧 Améliorations Immédiates (Haute Priorité)

1. **Upgrader le hachage des mots de passe**
   ```bash
   pip install argon2-cffi
   ```
   - Remplacer SHA256 par Argon2
   - Ajouter salt automatique

2. **Sécuriser les Secrets**
   ```bash
   # Créer un fichier .env
   DB_PASSWORD=your-secure-password
   FLASK_SECRET_KEY=your-secret-key
   ```

3. **Activer HTTPS/TLS**
   - Utiliser Let's Encrypt pour les certificats
   - Redirection HTTP → HTTPS

4. **Implémenter CORS Correctement**
   ```python
   from flask_cors import CORS
   CORS(app, origins=["https://trusted-domain.com"])
   ```

5. **Ajouter JWT pour Authentification**
   ```python
   from flask_jwt_extended import JWTManager, create_access_token
   jwt = JWTManager(app)
   ```

### 🔧 Améliorations À Moyen Terme

6. **Implémenter le Monitoring**
   - ELK Stack (Elasticsearch, Logstash, Kibana)
   - Alerting sur anomalies

7. **Compléter les Modules de Détection**
   - Machine Learning pour anomaly detection
   - Threat intelligence feeds

8. **API Rate Limiting Intelligent**
   - Par utilisateur/API key
   - Adapter selon le profil d'accès

9. **Audit Logging Complète**
   - Qui a fait quoi et quand
   - Immuable (logs dans base séparée)

10. **Chiffrement des Données Sensibles**
    - Chiffrement AES-256 pour emails/numéros de carte
    - Clés de chiffrement externes (HashiCorp Vault)

---

## 7. Checklist de Sécurité en Production

- [ ] HTTPS/TLS activé
- [ ] Secrets dans .env ou Vault
- [ ] Hachage Argon2 pour mots de passe
- [ ] JWT pour authentification stateless
- [ ] Rate limiting adapté au load
- [ ] Logging et monitoring complets
- [ ] Backup automatisés (PostgreSQL)
- [ ] Firewalls configurés (WAF)
- [ ] Audit logging activé
- [ ] Pentest réalisé
- [ ] Secrets pas en Git (`.gitignore`)
- [ ] Container scanning (Trivy/Snyk)
- [ ] RBAC/ABAC implémenté
- [ ] Validations d'input strictes
- [ ] Tests de sécurité (OWASP TOP 10)

---

## 8. Attaques Présentes dans le Dossier `/attacks/`

Le système inclut des scripts pour tester les vulnérabilités:

- **`sql_injection.py`** - Test injection SQL
- **`xss_attack.py`** - Test Cross-Site Scripting

Ces scripts sont utilisés à fin **éducationnelle** pour tester la robustesse du système.

---

## 9. Conclusion

Le système **Secure API Gateway** implémente une architecture **multi-couches** avec:
- ✅ Isolation des services (Docker)
- ✅ Limitation de débit (Rate Limiting)
- ✅ Filtrage d'IP (Blacklist)
- ✅ Authentification (SHA256)
- ✅ Isolation réseau
- ⚠️ À améliorer: Hachage passwords, HTTPS, Secrets management

**Niveau de Sécurité:** Modéré à Bon (pour apprentissage) - **CRITIQUE:** À renforcer avant production

---

**Dernière mise à jour:** Mars 2026  
**Responsable:** Projet Sécurité Cyber Mr Zinedine
