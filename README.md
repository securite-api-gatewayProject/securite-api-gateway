# Secure API Gateway 🚀

Une infrastructure microservices containerisée avec API Gateway pour démontrer les patterns de sécurité moderne.

## ✨ Caractéristiques

- **API Gateway (Kong)** : Routage centralisé, rate limiting, IP filtering
- **Microservices Flask** : user-service & payment-service indépendants
- **PostgreSQL** : Persistance des données (users, payments)
- **Docker Compose** : Déploiement simplifié (5 conteneurs orchestrés)
- **Sécurité** : Rate limiting (5 req/min), IP blacklist, password hashing SHA256

## 🏗️ Architecture

```
CLIENT (localhost:8000)
    ↓
KONG API GATEWAY (port 8000)
├─ Rate Limiting (5 req/min)
├─ IP Restriction
└─ Routing Rules
    ├─ /users → user-service:5001
    ├─ /payments → payment-service:5002
    └─ /mock → nginx:80
        ↓
PostgreSQL (5432)
├─ users table
└─ payments table
```

## 🚀 Démarrage rapide

### Prérequis
- Docker Desktop installé
- Minimum 2 GB RAM libre
- PowerShell / Terminal

### Installation

```powershell
# 1. Cloner le projet
git clone https://github.com/securite-api-gatewayProject/securite-api-gateway.git
cd securite-api-gateway

# 2. Naviguer vers infra
cd infra

# 3. Démarrer Docker Compose
docker-compose up --build

# 4. Attendre le message "services are running" (~30-60s)
```

## 🧪 Tests

Une fois démarré, tester dans un autre terminal :

```bash
# Via Kong Gateway (port 8000)
curl http://localhost:8000/users
curl http://localhost:8000/payments

# Direct aux services (ports 5001, 5002)
curl http://localhost:5001/users
curl http://localhost:5002/payments

# Login
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"password123"}'

# Créer paiement
curl -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1",
    "amount": 99.99,
    "currency": "EUR",
    "method": "credit_card",
    "description": "Test"
  }'
```

## 📊 Structure du projet

```
securite-api-gateway/
├── infra/
│   ├── docker-compose.yml       # Orchestration des services
│   └── kong.yml                 # Configuration Kong
│
├── microservices/
│   ├── user-service/            # Gestion utilisateurs (5001)
│   │   ├── user-service.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── payment-service/         # Gestion paiements (5002)
│       ├── payment-service.py
│       ├── Dockerfile
│       └── requirements.txt
│
├── attacks/                     # Tests d'attaque (à implémenter)
│   ├── sql_injection.py
│   └── xss_attack.py
│
├── threat-intel/                # Détection sécurité (à implémenter)
│   ├── anomaly_detector.py
│   └── ip_blocker.py
│
├── docs/
│   └── architecture.md          # Documentation complète
│
├── .gitignore
├── README.md
└── LICENSE
```

## 📚 Documentation

- **[architecture.md](docs/architecture.md)** : Documentation technique complète
  - Vue d'ensemble & architecture
  - Endpoints détaillés
  - Instructions déploiement
  - Tests & validation
  - Troubleshooting
  - Roadmap phases 2-5

## 🔌 API Endpoints

### user-service (port 5001)

```
GET  /health                 # Statut service
GET  /users                  # Lister utilisateurs
GET  /users/<id>             # Détail utilisateur
POST /users/login            # Authentifier
POST /users/register         # Créer compte
```

### payment-service (port 5002)

```
GET  /health                 # Statut service
GET  /payments               # Lister paiements
GET  /payments/<id>          # Détail paiement
GET  /payments?status=X      # Filtrer par status
POST /payments               # Créer paiement
GET  /payments/user/<uid>    # Paiements d'un utilisateur
```

## 🔐 Sécurité

### Implémenté
✅ Rate limiting : 5 requêtes/minute  
✅ IP blacklist : Bloquer 1.2.3.4 (test)  
✅ Password hashing : SHA256  
✅ SQL injection protection : Requêtes paramétrées (ORM)  
✅ CORS ready : Kong peut ajouter CORS headers  

### À venir
⚠️ JWT Tokens (remplacer UUID)  
⚠️ HTTPS/TLS  
⚠️ OAuth2 / OpenID Connect  
⚠️ Audit logging  
⚠️ Threat intelligence  

## 🛠️ Commandes utiles

```powershell
# Démarrer
cd infra
docker-compose up --build

# Voir logs temps réel
docker-compose logs -f

# Voir logs spécifiques
docker-compose logs -f kong
docker-compose logs -f user-service

# Redémarrer un service
docker-compose restart user-service

# Arrêter tout
docker-compose down

# Arrêter + reset données
docker-compose down -v

# Exécuter une commande dans conteneur
docker-compose exec postgres psql -U postgres -d api_gateway
```

## 📊 État du projet

| Composant | Status | Progression |
|-----------|--------|-------------|
| Infrastructure | ✅ | 100% |
| user-service | ✅ | 100% |
| payment-service | ✅ | 100% |
| Kong Gateway | ✅ | 100% |
| Sécurité basique | ✅ | 40% |
| Tests offensifs | ❌ | 0% |
| Threat intel | ❌ | 0% |
| **TOTAL** | ✅ | **70%** |

## 🌱 Données initiales

### Users
```
1. alice   / alice@example.com   / password123  / admin
2. bob     / bob@example.com     / secret456    / user
3. charlie / charlie@example.com / mypassword   / user
```

### Payments
```
pay_001: alice, 150€, credit_card, completed
pay_002: bob, 49.99€, paypal, completed
pay_003: alice, 200$, bank_transfer, pending
```

## 🚨 Troubleshooting

### Kong retourne 404
```powershell
docker-compose restart kong
docker-compose logs kong
```

### PostgreSQL ne démarre pas
```powershell
docker-compose down -v
docker-compose up --build
```

### Port déjà utilisé
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

Pour plus de détails : voir [architecture.md](docs/architecture.md)

## 📝 License

Educational Purpose  
Projet Cybersécurité - Semestre 2, 2026

## 🤝 Contribution

Les PR sont bienvenues ! Priorité :
1. Implémenter JWT tokens
2. Ajouter tests SQLi/XSS
3. Threat intelligence (anomaly detection)
4. Tests unitaires (pytest)

## 📞 Support

Pour toute question, consulter [architecture.md](docs/architecture.md) ou créer une issue Git.

---

**Dernière mise à jour:** 14 Mars 2026  
**Version:** 1.0 (MVP)  
**Status:** ✅ Fonctionnel & Déployable
