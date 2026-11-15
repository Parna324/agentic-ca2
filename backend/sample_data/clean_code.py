"""
Sample clean code for demonstrating APPROVE workflow.
This module implements a simple user authentication service.
"""
import hashlib
import secrets
from typing import Optional


def hash_password(password: str, salt: Optional[str] = None) -> tuple:
    """Hash a password using SHA-256 with a random salt."""
    if salt is None:
        salt = secrets.token_hex(32)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify a password against its hash."""
    computed, _ = hash_password(password, salt)
    return secrets.compare_digest(computed, hashed)


def get_user_by_email(db_session, email: str) -> Optional[dict]:
    """Look up a user by email using parameterized queries."""
    result = db_session.execute(
        "SELECT id, email, name FROM users WHERE email = :email",
        {"email": email}
    ).fetchone()
    return dict(result) if result else None


def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculate discounted price with input validation."""
    if price < 0:
        raise ValueError("Price cannot be negative")
    if not 0 <= discount_percent <= 100:
        raise ValueError("Discount must be between 0 and 100")
    return price * (1 - discount_percent / 100)


def test_hash_password():
    """Test password hashing."""
    h, s = hash_password("mypassword")
    assert verify_password("mypassword", h, s)
    assert not verify_password("wrongpassword", h, s)


def test_calculate_discount():
    """Test discount calculation."""
    assert calculate_discount(100.0, 20.0) == 80.0
    try:
        calculate_discount(-10.0, 20.0)
        assert False, "Should raise"
    except ValueError:
        pass
