"""
user-service.py
───────────────
Microservice Flask — Gestion des utilisateurs avec Sécurité Renforcée
Fait partie du projet : Secure API Gateway

Changements de sécurité:
  ✅ Argon2 pour hachage des mots de passe (remplace SHA256)
  ✅ JWT pour authentification (remplace UUID factice)
  ✅ Variables d'environnement pour secrets
  ✅ CORS configuré
  ✅ Email validation
  ✅ Audit logging
  ✅ Debug mode désactivé

Endpoints:
  GET  /health            -> statut du service
  GET  /users             -> liste des utilisateurs (AUTH REQUIRED)
  GET  /users/<id>        -> détail d'un utilisateur (AUTH REQUIRED)
  POST /users/login       -> authentification
  POST /users/register    -> création de compte
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from email_validator import validate_email, EmailNotValidError
from datetime import datetime, timedelta
import uuid
import os
import logging
from pythonjsonlogger import jsonlogger

# ── Configuration Logging ──────────────────────────────────────
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

app = Flask(__name__)

# ── Configuration Flask & Sécurité ────────────────────────────
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/api_gateway"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)  # Tokens expire après 1h
app.config["JSON_SORT_KEYS"] = False

# ── CORS Configuration ─────────────────────────────────────────
CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "http://localhost:*").split(",")}})

# ── Initialisation ─────────────────────────────────────────────
db = SQLAlchemy(app)
jwt = JWTManager(app)
ph = PasswordHasher()  # Argon2 password hasher

# ── Modèle utilisateur ────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"
    
    id = db.Column(db.String(36), primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self, include_password=False):
        """Convertit l'utilisateur en dictionnaire. JAMAIS inclure le hash du password."""
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
    
    def set_password(self, password: str):
        """Hash le mot de passe avec Argon2."""
        self.password_hash = ph.hash(password)
    
    def verify_password(self, password: str) -> bool:
        """Vérifie le mot de passe avec Argon2."""
        try:
            ph.verify(self.password_hash, password)
            return True
        except (VerifyMismatchError, InvalidHash):
            return False


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
                role="admin",
            ),
            User(
                id="2",
                username="bob",
                email="bob@example.com",
                role="user",
            ),
            User(
                id="3",
                username="charlie",
                email="charlie@example.com",
                role="user",
            ),
        ]
        # Hash les mots de passe avec Argon2
        for user in default_users:
            if user.username == "alice":
                user.set_password("password123")
            elif user.username == "bob":
                user.set_password("secret456")
            elif user.username == "charlie":
                user.set_password("mypassword")
        
        db.session.add_all(default_users)
        db.session.commit()
        logger.info(f"Default users created: {len(default_users)} users")


# ── Routes ─────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Health check pour Docker et Kong."""
    return jsonify({
        "status": "healthy",
        "service": "user-service",
        "timestamp": datetime.utcnow().isoformat(),
    }), 200


@app.route("/users", methods=["GET"])
@jwt_required()  # ✅ REQUIRE JWT TOKEN
def get_users():
    """Retourne la liste de tous les utilisateurs (AUTH REQUIRED)."""
    current_user_id = get_jwt_identity()
    logger.info(f"User {current_user_id} fetched users list")
    
    users = User.query.all()
    return jsonify({
        "users": [u.to_dict() for u in users],
        "count": len(users),
    }), 200


@app.route("/users/<user_id>", methods=["GET"])
@jwt_required()  # ✅ REQUIRE JWT TOKEN
def get_user(user_id: str):
    """Retourne un utilisateur par son ID (AUTH REQUIRED)."""
    current_user_id = get_jwt_identity()
    logger.info(f"User {current_user_id} requested user {user_id}")
    
    user = User.query.get(user_id)
    if not user:
        logger.warning(f"User {user_id} not found (requested by {current_user_id})")
        return jsonify({"error": "User not found", "id": user_id}), 404
    return jsonify(user.to_dict()), 200


@app.route("/users/login", methods=["POST"])
def login():
    """
    Authentification d'un utilisateur et génération JWT.
    Body JSON: { "username": "alice", "password": "password123" }
    
    Returns: { "access_token": "eyJ0eXAi...", "user": {...} }
    """
    data = request.get_json()
    if not data:
        logger.warning("Login attempt without JSON body")
        return jsonify({"error": "JSON body required"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        logger.warning(f"Login attempt with missing credentials from IP {request.remote_addr}")
        return jsonify({"error": "username and password are required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.verify_password(password):
        logger.warning(f"Failed login attempt for user {username} from IP {request.remote_addr}")
        return jsonify({"error": "Invalid credentials"}), 401

    # ✅ Create JWT token (expires in 1 hour)
    access_token = create_access_token(
        identity=user.id,
        additional_claims={
            "username": user.username,
            "role": user.role,
        }
    )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    logger.info(f"Successful login for user {username} from IP {request.remote_addr}")
    
    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "user": user.to_dict(),
    }), 200


@app.route("/users/register", methods=["POST"])
def register():
    """
    Création d'un nouveau compte.
    Body JSON: { "username": "...", "email": "...", "password": "..." }
    
    Sécurité: 
    - Email validated
    - Password hashed with Argon2
    """
    data = request.get_json()
    if not data:
        logger.warning("Registration attempt without JSON body")
        return jsonify({"error": "JSON body required"}), 400

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    # Validation
    if not all([username, email, password]):
        logger.warning(f"Registration attempt with missing fields from IP {request.remote_addr}")
        return jsonify({"error": "username, email and password are required"}), 400
    
    if len(username) < 3:
        return jsonify({"error": "username must be at least 3 characters"}), 400
    
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400
    
    # ✅ Validate email format
    try:
        validate_email(email)
    except EmailNotValidError:
        logger.warning(f"Invalid email format: {email} from IP {request.remote_addr}")
        return jsonify({"error": "Invalid email format"}), 400

    existing = User.query.filter_by(username=username).first()
    if existing:
        logger.warning(f"Registration attempt with existing username: {username}")
        return jsonify({"error": "Username already taken"}), 409
    
    existing_email = User.query.filter_by(email=email).first()
    if existing_email:
        logger.warning(f"Registration attempt with existing email: {email}")
        return jsonify({"error": "Email already registered"}), 409

    new_user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        role="user",
    )
    
    # ✅ Hash password with Argon2
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    logger.info(f"New user registered: {username} (email: {email})")

    return jsonify({
        "message": "User created successfully",
        "user": new_user.to_dict(),
    }), 201


@app.errorhandler(401)
def unauthorized(e):
    """Handle JWT errors."""
    logger.warning(f"Unauthorized access attempt: {e}")
    return jsonify({"error": "Unauthorized", "message": "Valid JWT token required"}), 401


@app.errorhandler(403)
def forbidden(e):
    """Handle forbidden access."""
    logger.warning(f"Forbidden access attempt: {e}")
    return jsonify({"error": "Forbidden"}), 403


@app.errorhandler(500)
def internal_error(e):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {e}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    # ✅ Debug mode controlled by environment variable
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=5001, debug=debug_mode)
