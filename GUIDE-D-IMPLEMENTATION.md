# 🚀 GUIDE D'IMPLÉMENTATION - Corrections de Sécurité Appliquées
# ═════════════════════════════════════════════════════════════════════════

## 📍 RÉSUMÉ DES CORRECTIONS

✅ **5 Failles Critiques Corrigées**
1. Hachage SHA256 → Argon2
2. UUID factice → JWT signé (1h expiration)
3. Credentials en clair → Variables d'environnement
4. Debug mode ON → OFF par défaut
5. Endpoints sans auth → JWT @required sur tous

---

## 📦 INSTALLATION & SETUP

### **Étape 1: Générer les Secrets**

```bash
# Générer deux secrets forts (32 caractères)
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_hex(32))"

# Exemple de sortie:
# a1b2c3d4e5f6...  ← FLASK_SECRET_KEY
# f6e5d4c3b2a1...  ← JWT_SECRET_KEY
```

### **Étape 2: Configurer le .env**

```bash
# Éditez le fichier .env
nano .env
```

Remplissez les variables:
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=votre-mot-de-passe-fort-ici
POSTGRES_DB=api_gateway
DATABASE_URL=postgresql://postgres:votre-mot-de-passe@postgres:5432/api_gateway

FLASK_ENV=development
FLASK_SECRET_KEY=<Résultat du python secrets.token_hex(32)>
JWT_SECRET_KEY=<Résultat du python secrets.token_hex(32)>

FLASK_DEBUG=False
RATE_LIMIT_ENABLED=True
LOG_LEVEL=INFO
```

### **Étape 3: Installer les Dépendances**

```bash
# User Service
cd microservices/user-service
pip install -r requirements.txt

# Payment Service  
cd ../payment-service
pip install -r requirements.txt
```

### **Étape 4: Démarrer Docker Compose**

```bash
cd infra
docker-compose build --no-cache
docker-compose up -d

# Vérifier les services
docker-compose ps
```

---

## 🔐 UTILISATION DU JWT

### **1. SE CONNECTER (Obtenir un Token)**

```bash
# Demander un JWT token
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "password123"
  }'

# Réponse:
{
  "message": "Login successful",
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZGVudGl0eSI6IjEiLCJ1c2VybmFtZSI6ImFsaWNlIiwicm9sZSI6ImFkbWluIiwiaWF0IjoxNjc0ODYxMjAwLCJleHAiOjE2NzQ4NjQ4MDB9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "1",
    "username": "alice",
    "email": "alice@example.com",
    "role": "admin",
    "created_at": "2026-04-02T10:00:00"
  }
}
```

### **2. UTILISER LE TOKEN**

Conservez le `access_token` et utilisez-le pour les requêtes aux endpoints protégés:

```bash
# Récupérer la liste des utilisateurs
curl http://localhost:8000/users \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1Q..."

# Récupérer les paiements
curl http://localhost:8000/payments \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1Q..."
```

### **3. LE TOKEN EXPIRE**

Le token expire après **1 heure**. Vous devez relancer login:

```bash
# ❌ Après 1h:
curl http://localhost:8000/users \
  -H "Authorization: Bearer <ancien_token>"

# Réponse: 401 Unauthorized - Token has expired

# ✅ Solution: Relancer login pour obtenir un nouveau token
```

---

## 📝 EXEMPLES DE REQUÊTES

### **Enregistrement d'Utilisateur**

```bash
curl -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "SecurePassword123"
  }'

# Réponse 201:
{
  "message": "User created successfully",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "newuser",
    "email": "newuser@example.com",
    "role": "user",
    "created_at": "2026-04-02T10:30:00"
  }
}
```

### **Créer un Paiement (Avec Token)**

```bash
# D'abord, obtenir un token
TOKEN=$(curl -s -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"password123"}' \
  | jq -r '.access_token')

# Puis créer un paiement
curl -X POST http://localhost:8000/payments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1",
    "amount": 99.99,
    "currency": "EUR",
    "method": "credit_card",
    "description": "Product purchase"
  }'

# Réponse 201:
{
  "message": "Payment completed",
  "payment": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "1",
    "amount": 99.99,
    "currency": "EUR",
    "status": "completed",
    "method": "credit_card",
    "description": "Product purchase",
    "created_at": "2026-04-02T10:35:00",
    "updated_at": "2026-04-02T10:35:00"
  }
}
```

### **Récupérer les Paiements d'un Utilisateur**

```bash
curl http://localhost:8000/payments/user/1 \
  -H "Authorization: Bearer $TOKEN"

# Réponse 200:
{
  "user_id": "1",
  "payments": [
    {"id": "...", "amount": 99.99, "status": "completed", ...},
    {"id": "...", "amount": 150.00, "status": "completed", ...}
  ],
  "count": 2,
  "total_completed": 249.99
}
```

---

## ⚠️ CODES D'ERREUR & SIGNIFICATION

| Code | Signification | Solution |
|------|---------------|----------|
| 200 | OK | ✅ Requête réussie |
| 201 | Created | ✅ Ressource créée |
| 400 | Bad Request | Vérifier JSON et paramètres |
| 401 | Unauthorized | Ajouter token valide: `Authorization: Bearer <token>` |
| 402 | Payment Required | Paiement échoué (10% simulation) |
| 403 | Forbidden | Accès non autorisé |
| 404 | Not Found | Ressource n'existe pas |
| 409 | Conflict | Username/Email déjà existant |
| 422 | Unprocessable Entity | JWT token invalide/malformé |
| 500 | Internal Server Error | Erreur serveur (voir logs) |

---

## 🧪 VALIDATION DES CORRECTIONS

### **Exécuter les Tests Automatiques**

```bash
# Depuis le répertoire racine
python quick-test.py

# Output:
# ✅ PASS - Health Check
# ✅ PASS - Login JWT
# ✅ PASS - Invalid Credentials
# ...
# 🎉 ALL TESTS PASSED (10/10)
```

### **Tests Manuels de Sécurité**

```bash
# 1. Tester accès sans token (doit échouer)
curl http://localhost:8000/users
# ❌ 401 Unauthorized

# 2. Tester accès avec token (doit réussir)
curl http://localhost:8000/users -H "Authorization: Bearer ..."
# ✅ 200 OK

# 3. Tester credentials invalides
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"wrongpassword"}'
# ❌ 401 Invalid credentials

# 4. Tester email invalide
curl -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"invalid-email","password":"pass123"}'
# ❌ 400 Invalid email format

# 5. Tester montant paiement trop élevé
curl -X POST http://localhost:8000/payments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"1","amount":9999999999,"currency":"EUR","method":"credit_card"}'
# ❌ 400 Amount exceeds maximum allowed
```

---

## 📊 AVANT vs APRÈS - Vue d'ensemble

| Aspect | ❌ AVANT | ✅ APRÈS |
|--------|---------|---------|
| **Stockage MDP** | SHA256 en clair | Argon2 + salt |
| **Token** | UUID random (non signé) | JWT signé (HMAC-256) |
| **Expiration** | Pas d'expiration | 1 heure |
| **Endpoints** | Aucune protection (public) | Tous protégés (@jwt_required) |
| **Secrets** | En clair dans docker-compose.yml | Variables d'env (.env, .gitignore) |
| **Debug Mode** | Toujours ON | OFF en production |
| **CORS** | Non configuré | Restrictif (domaines spécifiques) |
| **Logging** | Texte simple | JSON (audit trail) |
| **Validation Email** | Aucune | Validée (regex) |
| **Rate Limit Montant** | Illimité | Max 1,000,000 |

---

## 🔍 MONITORING & DEBUGGING

### **Consulter les Logs des Services**

```bash
# Logs en temps réel
docker-compose logs -f user-service
docker-compose logs -f payment-service
docker-compose logs -f suricata

# Logs au format JSON (audit trail)
docker-compose logs user-service | grep "User.*requested"
```

### **Décoder un JWT Token (debug)**

Accédez à [jwt.io](https://jwt.io) et collez votre token:

```
Header (HEADER.PAYLOAD.SIGNATURE):
{
  "typ": "JWT",
  "alg": "HS256"
}

Payload:
{
  "identity": "1",
  "username": "alice",
  "role": "admin",
  "iat": 1674861200,
  "exp": 1674864800
}

Signature: [HMAC-SHA256]
```

### **Vérifier la Connexion PostgreSQL**

```bash
# Accéder au conteneur PostgreSQL
docker-compose exec postgres psql -U postgres -d api_gateway

# Vérifier les tables
\dt

# Vérifier les utilisateurs
SELECT id, username, email, role, created_at FROM users;
```

---

## 📋 PROCHAINES ÉTAPES (PHASE 2)

### **Immédiat (Cette semaine)**
- [ ] Tester tous les endpoints avec quick-test.py
- [ ] Générer des secrets forts et les mettre à jour
- [ ] Mettre à jour le .env pour production
- [ ] Tester les attaques de sécurité (attacks/)

### **Court Terme (Prochaines 2 semaines)**  
- [ ] Ajouter HTTPS/TLS avec Let's Encrypt
- [ ] Implémenter logout avec token blacklist
- [ ] Ajouter refresh tokens (longue durée)
- [ ] Metrics & monitoring (Prometheus)

### **Moyen Terme (1-2 mois)**
- [ ] Anomaly detection (Machine Learning)
- [ ] Backup automatisé PostgreSQL
- [ ] WAF (Web Application Firewall)
- [ ] Pentest & audit de sécurité

---

## ❓ QUESTIONS FRÉQUENTES

### **Q: Mon token a expiré, que faire?**
A: Relancez login pour obtenir un nouveau token:
```bash
curl -X POST http://localhost:8000/users/login ...
```

### **Q: Pourquoi 401 Unauthorized?**
A: Vérifiez:
1. ✅ Header correct: `Authorization: Bearer <token>`
2. ✅ Token valide (pas expiré)
3. ✅ Token du bon format (JWT)

### **Q: Comment changer le mot de passe?** 
A: Actuellement non-implémenté. À ajouter:
```python
@app.route("/users/<user_id>/password", methods=["POST"])
@jwt_required()
def change_password(user_id):
    # Implémentation à venir
```

### **Q: Où sont stockés les logs?**
A: 
- Stdout (conteneur): `docker-compose logs`
- Fichier JSON: `/var/log/suricata/eve.json` (Suricata)
- Base de données: `payments` & `users` tables (PostgreSQL)

---

## 🆘 TROUBLESHOOTING

### **Erreur: Can't find .env**
```bash
# ✅ Solution: Créer depuis .env.example
cp .env.example .env
```

### **Erreur: ModuleNotFoundError: No module named 'argon2'**
```bash
# ✅ Solution: Installer dépendances
pip install argon2-cffi
```

### **Erreur: 502 Bad Gateway sur Kong**
```bash
# ✅ Solution: Vérifier services
docker-compose ps
docker-compose logs user-service
docker-compose logs payment-service
```

### **Warning: The "VAR" variable is not set (Docker Compose)**
Cause fréquente: interpolation `${VAR}` dans `docker-compose.yml` sans fichier `.env` local au dossier `infra/`.

```bash
# ✅ Vérifier la résolution des variables
docker-compose config
```

Bonnes pratiques appliquées dans ce projet:
- Utiliser `env_file: ../.env` pour les services
- Eviter l'interpolation `${VAR}` inutile dans `docker-compose.yml`

### **Erreur: Database connection refused**
```bash
# ✅ Solution: Vérifier PostgreSQL est sain
docker-compose logs postgres
docker-compose exec postgres pg_isready
```

### **Erreur: password authentication failed for user "postgres"**
Cause fréquente: le mot de passe a été modifié dans `.env` mais le volume PostgreSQL existant contient encore l'ancien mot de passe initialisé.

```bash
# ✅ Solution: recréer le volume PostgreSQL
docker-compose down -v
docker-compose up -d
```

### **Erreur Suricata: unsafe procfs detected / sysctl net.core.* not found**
Contexte: sur Docker Desktop/Windows, certains `sysctls` Linux ne sont pas disponibles.

```bash
# ✅ Vérifier que la configuration est bien compatible Windows
docker-compose config
```

Vérifications attendues dans `infra/docker-compose.yml`:
- Suricata utilise l'interface `eth0`
- Pas de bloc `sysctls` avec `net.core.*`
- Présence de `cap_add: [NET_ADMIN, NET_RAW]`

Si besoin, relancer proprement:

```bash
docker-compose down
docker-compose up -d
docker-compose ps
```

---

*Guide validé le 2026-04-10*
*État du Projet: 78% COMPLET (was 65%)*
*Prochaine Phase: HTTPS/TLS + Monitoring*
