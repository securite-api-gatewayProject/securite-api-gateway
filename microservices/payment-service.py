"""
payment-service.py
──────────────────
Microservice Flask — Gestion des paiements
Fait partie du projet : Secure API Gateway

Endpoints:
  GET  /health                  -> statut du service
  GET  /payments                -> liste des paiements
  GET  /payments/<id>           -> détail d'un paiement
  POST /payments                -> créer un paiement
  GET  /payments/user/<user_id> -> paiements d'un utilisateur
"""

from flask import Flask, request, jsonify
from datetime import datetime
import uuid
import random

app = Flask(__name__)

# ── Base de données simulée en mémoire ──────────────────────────
PAYMENTS_DB = {
    "pay_001": {
        "id": "pay_001",
        "user_id": "1",
        "amount": 150.00,
        "currency": "EUR",
        "status": "completed",
        "method": "credit_card",
        "description": "Subscription Premium",
        "created_at": "2024-03-01T10:00:00",
    },
    "pay_002": {
        "id": "pay_002",
        "user_id": "2",
        "amount": 49.99,
        "currency": "EUR",
        "status": "completed",
        "method": "paypal",
        "description": "One-time purchase",
        "created_at": "2024-03-05T14:30:00",
    },
    "pay_003": {
        "id": "pay_003",
        "user_id": "1",
        "amount": 200.00,
        "currency": "USD",
        "status": "pending",
        "method": "bank_transfer",
        "description": "Enterprise license",
        "created_at": "2024-03-10T09:00:00",
    },
}

VALID_METHODS    = {"credit_card", "paypal", "bank_transfer", "crypto"}
VALID_CURRENCIES = {"EUR", "USD", "GBP", "MAD"}


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
def get_payments():
    """Retourne la liste de tous les paiements (filtre optionnel: ?status=completed)."""
    status_filter = request.args.get("status")
    payments = list(PAYMENTS_DB.values())

    if status_filter:
        payments = [p for p in payments if p["status"] == status_filter]

    return jsonify({
        "payments": payments,
        "count": len(payments),
    }), 200


@app.route("/payments/<payment_id>", methods=["GET"])
def get_payment(payment_id: str):
    """Retourne un paiement par son ID."""
    payment = PAYMENTS_DB.get(payment_id)
    if not payment:
        return jsonify({"error": "Payment not found", "id": payment_id}), 404
    return jsonify(payment), 200


@app.route("/payments", methods=["POST"])
def create_payment():
    """
    Crée un nouveau paiement.
    Body JSON:
      {
        "user_id": "1",
        "amount": 99.99,
        "currency": "EUR",
        "method": "credit_card",
        "description": "..."
      }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    user_id     = str(data.get("user_id", "")).strip()
    amount      = data.get("amount")
    currency    = data.get("currency", "EUR").upper()
    method      = data.get("method", "").lower()
    description = data.get("description", "Payment")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({"error": "amount must be a positive number"}), 400
    if currency not in VALID_CURRENCIES:
        return jsonify({"error": f"currency must be one of {VALID_CURRENCIES}"}), 400
    if method not in VALID_METHODS:
        return jsonify({"error": f"method must be one of {VALID_METHODS}"}), 400

    # Simulation traitement (succès 90% du temps)
    status = "completed" if random.random() > 0.1 else "failed"

    payment_id  = f"pay_{uuid.uuid4().hex[:8]}"
    new_payment = {
        "id": payment_id,
        "user_id": user_id,
        "amount": round(float(amount), 2),
        "currency": currency,
        "status": status,
        "method": method,
        "description": description,
        "created_at": datetime.utcnow().isoformat(),
    }
    PAYMENTS_DB[payment_id] = new_payment

    http_status = 201 if status == "completed" else 402
    return jsonify({
        "message": f"Payment {status}",
        "payment": new_payment,
    }), http_status


@app.route("/payments/user/<user_id>", methods=["GET"])
def get_payments_by_user(user_id: str):
    """Retourne tous les paiements d'un utilisateur."""
    user_payments = [p for p in PAYMENTS_DB.values() if p["user_id"] == user_id]

    total = sum(p["amount"] for p in user_payments if p["status"] == "completed")

    return jsonify({
        "user_id": user_id,
        "payments": user_payments,
        "count": len(user_payments),
        "total_completed": round(total, 2),
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)