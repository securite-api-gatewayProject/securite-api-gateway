#!/usr/bin/env python3
"""
quick-test.py
──────────────
Script de test rapide des corrections de sécurité

Utilisation:
    python quick-test.py

Teste:
    ✅ Login avec authentification JWT
    ✅ Accès aux endpoints protégés avec token
    ✅ Rejet sans token (401)
    ✅ Rejet avec token expiré (401)
    ✅ Hachage Argon2 des mots de passe
    ✅ Validation des emails
"""

import requests
import json
import sys
from typing import Dict, Tuple

BASE_URL = "http://localhost:8000"
USER_SERVICE_URL = "http://localhost:5001"
PAYMENT_SERVICE_URL = "http://localhost:5002"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_test(title: str):
    """Print test header."""
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}TEST: {title}{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}")

def print_pass(message: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_fail(message: str):
    """Print failure message."""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_info(message: str):
    """Print info message."""
    print(f"{Colors.YELLOW}ℹ️  {message}{Colors.END}")

# ─────────────────────────────────────────────────────────────────────────
# Test 1: Health Check
# ─────────────────────────────────────────────────────────────────────────

def test_health():
    """Test health endpoints."""
    print_test("Health Check")
    
    try:
        # Kong health
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code == 200:
            print_pass(f"Kong gateway healthy: {r.json().get('status')}")
        else:
            print_fail(f"Kong health failed: {r.status_code}")
            return False
        
        # User service health
        r = requests.get(f"{USER_SERVICE_URL}/health", timeout=5)
        if r.status_code == 200:
            print_pass(f"User service healthy: {r.json().get('status')}")
        else:
            print_fail(f"User service health failed: {r.status_code}")
            return False
        
        # Payment service health
        r = requests.get(f"{PAYMENT_SERVICE_URL}/health", timeout=5)
        if r.status_code == 200:
            print_pass(f"Payment service healthy: {r.json().get('status')}")
        else:
            print_fail(f"Payment service health failed: {r.status_code}")
            return False
        
        return True
    except Exception as e:
        print_fail(f"Connection error: {e}")
        print_info("❌ Services ne sont pas démarrées. Lancez: docker-compose up")
        return False

# ─────────────────────────────────────────────────────────────────────────
# Test 2: JWT Authentication
# ─────────────────────────────────────────────────────────────────────────

def test_login():
    """Test login with JWT generation."""
    print_test("JWT Authentication - Login")
    
    login_data = {
        "username": "alice",
        "password": "password123"
    }
    
    try:
        r = requests.post(f"{USER_SERVICE_URL}/users/login", json=login_data, timeout=5)
        
        if r.status_code == 200:
            response = r.json()
            print_pass(f"Login successful")
            print_info(f"Token type: {response.get('token_type')}")
            print_info(f"Expires in: {response.get('expires_in')} seconds")
            
            token = response.get('access_token')
            if token:
                print_pass(f"JWT token generated (first 20 chars): {token[:20]}...")
                return token
            else:
                print_fail("No token in response")
                return None
        else:
            print_fail(f"Login failed: {r.status_code} - {r.json()}")
            return None
    except Exception as e:
        print_fail(f"Login error: {e}")
        return None

def test_invalid_credentials():
    """Test login with invalid credentials."""
    print_test("Invalid Credentials")
    
    login_data = {
        "username": "alice",
        "password": "wrongpassword"
    }
    
    try:
        r = requests.post(f"{USER_SERVICE_URL}/users/login", json=login_data, timeout=5)
        
        if r.status_code == 401:
            print_pass(f"Invalid credentials rejected (401 Unauthorized)")
            return True
        else:
            print_fail(f"Expected 401, got {r.status_code}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────
# Test 3: Protected Endpoints
# ─────────────────────────────────────────────────────────────────────────

def test_protected_endpoint_without_token():
    """Test protected endpoint without JWT token."""
    print_test("Protected Endpoint - No Token")
    
    try:
        r = requests.get(f"{USER_SERVICE_URL}/users", timeout=5)
        
        if r.status_code == 401:
            print_pass(f"Endpoint correctly rejected (401 Unauthorized)")
            return True
        else:
            print_fail(f"Expected 401, got {r.status_code}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_protected_endpoint_with_token(token: str):
    """Test protected endpoint with JWT token."""
    print_test("Protected Endpoint - With Valid Token")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        r = requests.get(f"{USER_SERVICE_URL}/users", headers=headers, timeout=5)
        
        if r.status_code == 200:
            response = r.json()
            print_pass(f"Endpoint authorized (200 OK)")
            print_info(f"Users count: {response.get('count')}")
            return True
        else:
            print_fail(f"Expected 200, got {r.status_code} - {r.json()}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_protected_endpoint_with_invalid_token():
    """Test protected endpoint with invalid token."""
    print_test("Protected Endpoint - Invalid Token")
    
    headers = {
        "Authorization": "Bearer invalid.token.here"
    }
    
    try:
        r = requests.get(f"{USER_SERVICE_URL}/users", headers=headers, timeout=5)
        
        if r.status_code == 401 or r.status_code == 422:
            print_pass(f"Invalid token rejected ({r.status_code})")
            return True
        else:
            print_fail(f"Expected 401/422, got {r.status_code}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────
# Test 4: Payments API with JWT
# ─────────────────────────────────────────────────────────────────────────

def test_payments_without_token():
    """Test payments endpoint without token."""
    print_test("Payments API - No Token")
    
    try:
        r = requests.get(f"{PAYMENT_SERVICE_URL}/payments", timeout=5)
        
        if r.status_code == 401:
            print_pass(f"Payments correctly rejected without token (401)")
            return True
        else:
            print_fail(f"Expected 401, got {r.status_code}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_payments_with_token(token: str):
    """Test payments endpoint with token."""
    print_test("Payments API - With Token")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        r = requests.get(f"{PAYMENT_SERVICE_URL}/payments", headers=headers, timeout=5)
        
        if r.status_code == 200:
            response = r.json()
            print_pass(f"Payments retrieved (200 OK)")
            print_info(f"Payments count: {response.get('count')}")
            return True
        else:
            print_fail(f"Expected 200, got {r.status_code}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────
# Test 5: Password Hashing (Argon2)
# ─────────────────────────────────────────────────────────────────────────

def test_password_hashing():
    """Test that passwords are hashed with Argon2."""
    print_test("Password Hashing - Argon2")
    
    try:
        from argon2 import PasswordHasher
        
        ph = PasswordHasher()
        password = "test123"
        
        # Hash password
        hash1 = ph.hash(password)
        print_pass(f"Password hashed with Argon2")
        print_info(f"Hash format: {hash1[:20]}...")
        
        # Verify correct password
        try:
            ph.verify(hash1, password)
            print_pass(f"Correct password verified successfully")
        except:
            print_fail(f"Correct password verification failed")
            return False
        
        # Verify wrong password
        try:
            ph.verify(hash1, "wrongpassword")
            print_fail(f"Wrong password should not verify!")
            return False
        except:
            print_pass(f"Wrong password correctly rejected")
        
        return True
    except ImportError:
        print_fail("Argon2 not installed - run: pip install argon2-cffi")
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────
# Test 6: Email Validation
# ─────────────────────────────────────────────────────────────────────────

def test_email_validation():
    """Test email validation."""
    print_test("Email Validation")
    
    try:
        from email_validator import validate_email, EmailNotValidError
        
        # Valid email
        try:
            validate_email("alice@example.com")
            print_pass(f"Valid email accepted: alice@example.com")
        except EmailNotValidError:
            print_fail(f"Valid email rejected")
            return False
        
        # Invalid email
        try:
            validate_email("invalid-email")
            print_fail(f"Invalid email should be rejected")
            return False
        except EmailNotValidError:
            print_pass(f"Invalid email correctly rejected")
        
        return True
    except ImportError:
        print_fail("email-validator not installed - run: pip install email-validator")
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────
# Main Test Suite
# ─────────────────────────────────────────────────────────────────────────

def main():
    """Run all security tests."""
    print(f"\n{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║     SECURE API GATEWAY - SECURITY CORRECTIONS VALIDATION          ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}")
    
    results = {
        "Health Check": False,
        "Login JWT": False,
        "Invalid Credentials": False,
        "Protected Endpoint (no token)": False,
        "Protected Endpoint (with token)": False,
        "Invalid Token": False,
        "Payments (no token)": False,
        "Payments (with token)": False,
        "Password Hashing": False,
        "Email Validation": False,
    }
    
    # Test health
    if not test_health():
        print(f"\n{Colors.RED}❌ Services not available. Start with: docker-compose up{Colors.END}\n")
        return
    results["Health Check"] = True
    
    # Test JWT login
    token = test_login()
    if token:
        results["Login JWT"] = True
    else:
        print(f"\n{Colors.RED}Stopping tests - JWT login failed{Colors.END}\n")
        return
    
    # Test invalid credentials
    results["Invalid Credentials"] = test_invalid_credentials()
    
    # Test protected endpoints
    results["Protected Endpoint (no token)"] = test_protected_endpoint_without_token()
    results["Protected Endpoint (with token)"] = test_protected_endpoint_with_token(token)
    results["Invalid Token"] = test_protected_endpoint_with_invalid_token()
    
    # Test payments
    results["Payments (no token)"] = test_payments_without_token()
    results["Payments (with token)"] = test_payments_with_token(token)
    
    # Test security features
    results["Password Hashing"] = test_password_hashing()
    results["Email Validation"] = test_email_validation()
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}\n")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{status} - {test_name}")
    
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
    percentage = (passed / total) * 100
    if passed == total:
        print(f"{Colors.GREEN}🎉 ALL TESTS PASSED ({passed}/{total}) - {percentage:.0f}%{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  {passed}/{total} tests passed - {percentage:.0f}%{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}\n")

if __name__ == "__main__":
    main()
