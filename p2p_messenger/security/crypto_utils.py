"""
Crypto utilities for P2P Messenger
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import load_pem_x509_certificate
import os


def generate_rsa_keypair(key_size: int = 3072) -> Tuple:
    """Generate RSA key pair"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    return private_key, public_key


def generate_ec_keypair():
    """Generate ECC key pair for ECDH"""
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()
    return private_key, public_key


def compute_fingerprint(data: bytes) -> str:
    """Compute SHA256 fingerprint"""
    return hashlib.sha256(data).hexdigest()


def serialize_public_key(public_key) -> bytes:
    """Serialize public key to PEM format"""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )


def deserialize_public_key(data: bytes):
    """Deserialize public key from PEM format"""
    return serialization.load_pem_public_key(data, backend=default_backend())


def serialize_private_key(private_key) -> bytes:
    """Serialize private key to PEM format"""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )


def deserialize_private_key(data: bytes):
    """Deserialize private key from PEM format"""
    return serialization.load_pem_private_key(
        data,
        password=None,
        backend=default_backend()
    )


def derive_shared_secret(private_key, peer_public_key) -> bytes:
    """Derive shared secret using ECDH"""
    if isinstance(private_key, ec.EllipticCurvePrivateKey):
        return private_key.exchange(ec.ECDH(), peer_public_key)
    else:
        # For RSA, we'll use a different approach
        raise ValueError("Only ECC keys supported for ECDH")


def derive_keys(shared_secret: bytes) -> Tuple[bytes, bytes]:
    """Derive encryption and MAC keys from shared secret"""
    # Simple key derivation - in production use HKDF
    hash_obj = hashlib.sha256(shared_secret)
    derived = hash_obj.digest()
    encryption_key = derived[:32]  # AES-256
    mac_key = derived[32:]  # HMAC-SHA256
    return encryption_key, mac_key


def encrypt_aes_gcm(plaintext: bytes, key: bytes, nonce: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
    """Encrypt data using AES-GCM"""
    if nonce is None:
        nonce = os.urandom(12)  # 96-bit nonce
    
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    tag = encryptor.tag
    
    return ciphertext, nonce, tag


def decrypt_aes_gcm(ciphertext: bytes, key: bytes, nonce: bytes, tag: bytes) -> bytes:
    """Decrypt data using AES-GCM"""
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext


def compute_hmac(data: bytes, key: bytes) -> bytes:
    """Compute HMAC-SHA256"""
    import hmac
    return hmac.new(key, data, hashlib.sha256).digest()


def verify_hmac(data: bytes, key: bytes, signature: bytes) -> bool:
    """Verify HMAC-SHA256"""
    expected = compute_hmac(data, key)
    return hmac.compare_digest(expected, signature)


def sign_data(data: bytes, private_key) -> bytes:
    """Sign data using RSA-PSS"""
    signature = private_key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature


def verify_signature(data: bytes, signature: bytes, public_key) -> bool:
    """Verify RSA-PSS signature"""
    try:
        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


def create_self_signed_certificate(user_id: str, user_name: str, private_key, 
                                    days_valid: int = 3650) -> Dict[str, Any]:
    """Create a self-signed certificate structure"""
    from datetime import datetime, timedelta
    
    public_key = private_key.public_key()
    
    cert_data = {
        'user_id': user_id,
        'user_name': user_name,
        'public_key_pem': serialize_public_key(public_key).decode('utf-8'),
        'created_at': datetime.utcnow().isoformat(),
        'expires_at': (datetime.utcnow() + timedelta(days=days_valid)).isoformat(),
        'version': 1
    }
    
    # Sign the certificate data
    data_to_sign = json.dumps(cert_data, sort_keys=True).encode('utf-8')
    signature = sign_data(data_to_sign, private_key)
    
    cert_data['signature'] = signature.hex()
    cert_data['fingerprint'] = compute_fingerprint(json.dumps(cert_data, sort_keys=True).encode('utf-8'))
    
    return cert_data


def verify_certificate(cert_data: Dict[str, Any], public_key=None) -> Tuple[bool, str]:
    """Verify a self-signed certificate"""
    try:
        # Check expiration
        expires_at = datetime.fromisoformat(cert_data['expires_at'])
        if datetime.utcnow() > expires_at:
            return False, "Certificate expired"
        
        # Get public key from cert or provided
        if public_key is None:
            public_key = deserialize_public_key(cert_data['public_key_pem'].encode('utf-8'))
        
        # Verify signature
        data_to_verify = json.dumps({
            'user_id': cert_data['user_id'],
            'user_name': cert_data['user_name'],
            'public_key_pem': cert_data['public_key_pem'],
            'created_at': cert_data['created_at'],
            'expires_at': cert_data['expires_at'],
            'version': cert_data['version']
        }, sort_keys=True).encode('utf-8')
        
        signature = bytes.fromhex(cert_data['signature'])
        
        if not verify_signature(data_to_verify, signature, public_key):
            return False, "Invalid signature"
        
        return True, "Valid"
    except Exception as e:
        return False, f"Verification error: {str(e)}"
