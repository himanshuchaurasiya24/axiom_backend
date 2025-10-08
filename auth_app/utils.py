import secrets
import base64
import hashlib

def generate_secure_token(length_bytes: int = 32) -> str:
    token_bytes = secrets.token_bytes(length_bytes)
    return base64.urlsafe_b64encode(token_bytes).decode('utf-8')

def hash_token(token: str, salt: str) -> str:
    salted_token = (salt + token).encode('utf-8')
    return hashlib.sha256(salted_token).hexdigest()