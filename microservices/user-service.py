"""
user-service.py
───────────────
Microservice Flask — Gestion des utilisateurs
Fait partie du projet : Secure API Gateway

Endpoints:
  GET  /health            -> statut du service
  GET  /users             -> liste des utilisateurs
  GET  /users/<id>        -> détail d'un utilisateur
  POST /users/login       -> authentification
  POST /users/register    -> création de compte
"""

from flask import Flask, request, jsonify
from datetime import datetime
import hashlib
import uuid

app = Flask(__name__)

# ── Base de données simulée en mémoire ──────────────────────────
USERS_DB = {
    "1": {
        "id": "1",
        "username": "alice",
        "email": "alice@example.com",
        "password_hash": hashlib.sha256("password123".encode()).hexdigest(),
        "role": "admin",
        "created_at": "2024-01-15T10:00:00",
    },
    "2": {
        "id": "2",
        "username": "bob",
        "email": "bob@example.com",
        "password_hash": hashlib.sha256("secret456".encode()).hexdigest(),
        "role": "user",
        "created_at": "2024-02-20T14:30:00",
    },
    "3": {
        "id": "3",
        "username": "charlie",
        "email": "charlie@example.com",
        "password_hash": hashlib.sha256("mypassword".encode()).hexdigest(),
        "role": "user",
        "created_at": "2024-03-05T09:15:00",
    },
}


def safe_user(user: dict) -> dict:
    """Retourne l'utilisateur sans le hash du mot de passe."""
    return {k: v for k, v in user.items() if k != "password_hash"}


# ── Routes ──────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Health check pour Docker et Kong."""
    return jsonify({
        "status": "healthy",
        "service": "user-service",
        "timestamp": datetime.utcnow().isoformat(),
    }), 200


@app.route("/users", methods=["GET"])
def get_users():
    """Retourne la liste de tous les utilisateurs."""
    users = [safe_user(u) for u in USERS_DB.values()]
    return jsonify({
        "users": users,
        "count": len(users),
    }), 200


@app.route("/users/<user_id>", methods=["GET"])
def get_user(user_id: str):
    """Retourne un utilisateur par son ID."""
    user = USERS_DB.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "id": user_id}), 404
    return jsonify(safe_user(user)), 200


@app.route("/users/login", methods=["POST"])
def login():
    """
    Authentification d'un utilisateur.
    Body JSON: { "username": "alice", "password": "password123" }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = next((u for u in USERS_DB.values() if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user["password_hash"] != password_hash:
        return jsonify({"error": "Invalid credentials"}), 401

    fake_token = str(uuid.uuid4())
    return jsonify({
        "message": "Login successful",
        "token": fake_token,
        "user": safe_user(user),
    }), 200


@app.route("/users/register", methods=["POST"])
def register():
    """
    Création d'un nouveau compte.
    Body JSON: { "username": "...", "email": "...", "password": "..." }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    username = data.get("username", "").strip()
    email    = data.get("email", "").strip()
    password = data.get("password", "")

    if not all([username, email, password]):
        return jsonify({"error": "username, email and password are required"}), 400

    existing = next((u for u in USERS_DB.values() if u["username"] == username), None)
    if existing:
        return jsonify({"error": "Username already taken"}), 409

    new_id = str(len(USERS_DB) + 1)
    new_user = {
        "id": new_id,
        "username": username,
        "email": email,
        "password_hash": hashlib.sha256(password.encode()).hexdigest(),
        "role": "user",
        "created_at": datetime.utcnow().isoformat(),
    }
    USERS_DB[new_id] = new_user

    return jsonify({
        "message": "User created successfully",
        "user": safe_user(new_user),
    }), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)