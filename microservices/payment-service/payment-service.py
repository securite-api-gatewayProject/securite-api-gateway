"""
payment-service.py
──────────────────
Microservice Flask — Gestion des paiements avec Sécurité Renforcée
Fait partie du projet : Secure API Gateway

Changements de sécurité:
  ✅ JWT obligatoire sur tous les endpoints
  ✅ CORS configuré
  ✅ Audit logging
  ✅ Validation stricte des montants
  ✅ Protection des données sensibles
  ✅ Debug mode désactivé

Endpoints:
  GET  /health                  -> statut du service
  GET  /payments                -> liste des paiements (AUTH REQUIRED)
  GET  /payments/<id>           -> détail d'un paiement (AUTH REQUIRED)
  POST /payments                -> créer un paiement (AUTH REQUIRED)
  GET  /payments/user/<user_id> -> paiements d'un utilisateur (AUTH REQUIRED)
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from flask_cors import CORS
from datetime import datetime, timedelta
import uuid
import random
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
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["JSON_SORT_KEYS"] = False

# ── CORS Configuration ─────────────────────────────────────────
CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "http://localhost:*").split(",")}})

# ── Initialisation ─────────────────────────────────────────────
db = SQLAlchemy(app)
jwt = JWTManager(app)

VALID_METHODS    = {"credit_card", "paypal", "bank_transfer", "crypto"}
VALID_CURRENCIES = {"EUR", "USD", "GBP", "MAD"}

# ──Modèle paiement ─────────────────────────────────────────────
class Payment(db.Model):
    __tablename__ = "payments"
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default="EUR")
    status = db.Column(db.String(20), default="pending")
    method = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convertit le paiement en dictionnaire (sans données sensibles)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": round(self.amount, 2),
            "currency": self.currency,
            "status": self.status,
            "method": self.method,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

# Créer les tables au démarrage
with app.app_context():
    db.create_all()
    # Remplir les données par défaut si vide
    if Payment.query.count() == 0:
        default_payments = [
            Payment(
                id=str(uuid.uuid4()),
                user_id="1",
                amount=150.00,
                currency="EUR",
                status="completed",
                method="credit_card",
                description="Subscription Premium",
            ),
            Payment(
                id=str(uuid.uuid4()),
                user_id="2",
                amount=49.99,
                currency="EUR",
                status="completed",
                method="paypal",
                description="One-time purchase",
            ),
            Payment(
                id=str(uuid.uuid4()),
                user_id="1",
                amount=200.00,
                currency="USD",
                status="pending",
                method="bank_transfer",
                description="Enterprise license",
            ),
        ]
        db.session.add_all(default_payments)
        db.session.commit()
        logger.info(f"Default payments created: {len(default_payments)} payments")


# ── Routes ──────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Health check pour Docker et Kong."""
    return jsonify({
        "status": "healthy",
        "service": "payment-service",
        "timestamp": datetime.utcnow().isoformat(),
    }), 200


@app.route("/payments", methods=["GET"])
@jwt_required()  # ✅ REQUIRE JWT TOKEN
def get_payments():
    """Retourne la liste de tous les paiements (filtre optionnel: ?status=completed) (AUTH REQUIRED)."""
    current_user_id = get_jwt_identity()
    status_filter = request.args.get("status")
    
    logger.info(f"User {current_user_id} fetched payments (filter: {status_filter})")
    
    query = Payment.query
    if status_filter:
        if status_filter not in ["pending", "completed", "failed"]:
            logger.warning(f"Invalid status filter: {status_filter} from user {current_user_id}")
            return jsonify({"error": "Invalid status filter"}), 400
        query = query.filter_by(status=status_filter)
    
    payments = query.all()
    return jsonify({
        "payments": [p.to_dict() for p in payments],
        "count": len(payments),
    }), 200


@app.route("/payments/<payment_id>", methods=["GET"])
@jwt_required()  # ✅ REQUIRE JWT TOKEN
def get_payment(payment_id: str):
    """Retourne un paiement par son ID (AUTH REQUIRED)."""
    current_user_id = get_jwt_identity()
    logger.info(f"User {current_user_id} requested payment {payment_id}")
    
    payment = Payment.query.get(payment_id)
    if not payment:
        logger.warning(f"Payment {payment_id} not found (requested by {current_user_id})")
        return jsonify({"error": "Payment not found", "id": payment_id}), 404
    
    # Optionnel: vérifier que l'user own ce payment
    # if payment.user_id != current_user_id:
    #     logger.warning(f"Unauthorized access to payment {payment_id} by user {current_user_id}")
    #     return jsonify({"error": "Unauthorized"}), 403
    
    return jsonify(payment.to_dict()), 200


@app.route("/payments", methods=["POST"])
@jwt_required()  # ✅ REQUIRE JWT TOKEN
def create_payment():
    """
    Crée un nouveau paiement (AUTH REQUIRED).
    Body JSON:
      {
        "user_id": "1",
        "amount": 99.99,
        "currency": "EUR",
        "method": "credit_card",
        "description": "..."
      }
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    if not data:
        logger.warning(f"Payment creation attempt without JSON body by user {current_user_id}")
        return jsonify({"error": "JSON body required"}), 400

    user_id     = str(data.get("user_id", "")).strip()
    amount      = data.get("amount")
    currency    = data.get("currency", "EUR").upper()
    method      = data.get("method", "").lower()
    description = data.get("description", "Payment")

    # Validation
    if not user_id:
        logger.warning(f"Payment creation without user_id by user {current_user_id}")
        return jsonify({"error": "user_id is required"}), 400
    
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        logger.warning(f"Invalid amount for payment by user {current_user_id}: {amount}")
        return jsonify({"error": "amount must be a positive number"}), 400
    
    if amount > 1000000:  # Limite anti-fraude
        logger.warning(f"Suspicious payment amount ({amount}) by user {current_user_id}")
        return jsonify({"error": "Amount exceeds maximum allowed"}), 400
    
    if currency not in VALID_CURRENCIES:
        logger.warning(f"Invalid currency {currency} by user {current_user_id}")
        return jsonify({"error": f"currency must be one of {VALID_CURRENCIES}"}), 400
    
    if method not in VALID_METHODS:
        logger.warning(f"Invalid method {method} by user {current_user_id}")
        return jsonify({"error": f"method must be one of {VALID_METHODS}"}), 400
    
    if len(description) > 255:
        logger.warning(f"Description too long by user {current_user_id}")
        return jsonify({"error": "description must be <= 255 characters"}), 400

    # Simulation traitement (succès 90% du temps)
    status = "completed" if random.random() > 0.1 else "failed"

    payment_id = str(uuid.uuid4())
    new_payment = Payment(
        id=payment_id,
        user_id=user_id,
        amount=round(float(amount), 2),
        currency=currency,
        status=status,
        method=method,
        description=description,
    )
    db.session.add(new_payment)
    db.session.commit()
    
    logger.info(f"Payment created: {payment_id} ({status}) by user {current_user_id}")

    http_status = 201 if status == "completed" else 402
    return jsonify({
        "message": f"Payment {status}",
        "payment": new_payment.to_dict(),
    }), http_status


@app.route("/payments/user/<user_id>", methods=["GET"])
@jwt_required()  # ✅ REQUIRE JWT TOKEN
def get_payments_by_user(user_id: str):
    """Retourne tous les paiements d'un utilisateur (AUTH REQUIRED)."""
    current_user_id = get_jwt_identity()
    
    logger.info(f"User {current_user_id} requested payments for user {user_id}")
    
    # Optionnel: vérifier que current_user_id == user_id
    # if current_user_id != user_id:
    #     logger.warning(f"Unauthorized access to payments for user {user_id} by user {current_user_id}")
    #     return jsonify({"error": "Unauthorized"}), 403
    
    user_payments = Payment.query.filter_by(user_id=user_id).all()
    total = sum(p.amount for p in user_payments if p.status == "completed")

    return jsonify({
        "user_id": user_id,
        "payments": [p.to_dict() for p in user_payments],
        "count": len(user_payments),
        "total_completed": round(total, 2),
    }), 200


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
    app.run(host="0.0.0.0", port=5002, debug=debug_mode)
