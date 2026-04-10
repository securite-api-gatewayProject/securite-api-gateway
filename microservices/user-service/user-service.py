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
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib
import uuid
import os

app = Flask(__name__)

# ── Configuration PostgreSQL ──────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/api_gateway"
)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ── Modèle utilisateur ────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"
    
    id = db.Column(db.String(36), primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self, include_password=False):
        """Convertit l'utilisateur en dictionnaire."""
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }
        if include_password:
            data["password_hash"] = self.password_hash
        return data

# Créer les tables au démarrage
with app.app_context():
    db.create_all()
    # Remplir les données par défaut si vide
    if User.query.count() == 0:
        default_users = [
            User(
                id="1",
                username="alice",
                email="alice@example.com",
                password_hash=hashlib.sha256("password123".encode()).hexdigest(),
                role="admin",
            ),
            User(
                id="2",
                username="bob",
                email="bob@example.com",
                password_hash=hashlib.sha256("secret456".encode()).hexdigest(),
                role="user",
            ),
            User(
                id="3",
                username="charlie",
                email="charlie@example.com",
                password_hash=hashlib.sha256("mypassword".encode()).hexdigest(),
                role="user",
            ),
        ]
        db.session.add_all(default_users)
        db.session.commit()


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
    users = User.query.all()
    return jsonify({
        "users": [u.to_dict() for u in users],
        "count": len(users),
    }), 200


@app.route("/users/<user_id>", methods=["GET"])
def get_user(user_id: str):
    """Retourne un utilisateur par son ID."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "id": user_id}), 404
    return jsonify(user.to_dict()), 200


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

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user.password_hash != password_hash:
        return jsonify({"error": "Invalid credentials"}), 401

    fake_token = str(uuid.uuid4())
    return jsonify({
        "message": "Login successful",
        "token": fake_token,
        "user": user.to_dict(),
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

    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({"error": "Username already taken"}), 409

    new_user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        password_hash=hashlib.sha256(password.encode()).hexdigest(),
        role="user",
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": "User created successfully",
        "user": new_user.to_dict(),
    }), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)