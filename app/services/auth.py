import bcrypt
import hashlib

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    # Encode password to bytes
    password_bytes = password.encode('utf-8')
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash"""
    # Encode to bytes
    password_bytes = password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    # Verify
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def hash_refresh_token(token: str) -> str:
    """Hash the refresh token before storing it"""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_refresh_token(stored_hash: str, provided_token: str) -> bool:
    """Check if provided refresh token matches stored hash"""
    return stored_hash == hash_refresh_token(provided_token)
