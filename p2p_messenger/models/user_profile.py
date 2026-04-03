"""
User Profile Model for P2P Messenger
Manages user identity, keys, and certificate
"""

import json
import os
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from ..security.crypto_utils import (
    generate_rsa_keypair, generate_ec_keypair,
    serialize_private_key, deserialize_private_key,
    create_self_signed_certificate, compute_fingerprint
)
from ..utils.constants import RSA_KEY_SIZE, CERT_VALIDITY_DAYS


class UserProfile:
    """Manages the local user's profile and cryptographic identity"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.profile_file = os.path.join(data_dir, 'profile.json')
        self.keys_file = os.path.join(data_dir, 'keys.json')
        
        self.user_id: Optional[str] = None
        self.user_name: Optional[str] = None
        self.avatar_path: Optional[str] = None
        self.created_at: Optional[str] = None
        
        self.rsa_private_key = None
        self.ec_private_key = None
        self.certificate: Optional[Dict[str, Any]] = None
        
        self._load_or_create()
    
    def _load_or_create(self):
        """Load existing profile or create new one"""
        if os.path.exists(self.profile_file):
            self._load_profile()
        else:
            # Profile doesn't exist - will be created via create_account()
            pass
    
    def _load_profile(self):
        """Load profile from disk"""
        try:
            with open(self.profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            
            self.user_id = profile_data.get('user_id')
            self.user_name = profile_data.get('user_name', 'User')
            self.avatar_path = profile_data.get('avatar_path')
            self.created_at = profile_data.get('created_at')
            
            # Load keys
            self._load_keys()
            
            # Load or create certificate
            if os.path.exists(self.keys_file):
                with open(self.keys_file, 'r', encoding='utf-8') as f:
                    keys_data = json.load(f)
                self.certificate = keys_data.get('certificate')
                
                if not self.certificate:
                    self._generate_keys_and_cert()
            else:
                self._generate_keys_and_cert()
                
        except Exception as e:
            print(f"Error loading profile: {e}")
            # Corrupted profile - will need to recreate
            self.user_id = None
    
    def _load_keys(self):
        """Load cryptographic keys from disk"""
        try:
            with open(self.keys_file, 'r', encoding='utf-8') as f:
                keys_data = json.load(f)
            
            # Load RSA private key
            rsa_key_pem = keys_data.get('rsa_private_key')
            if rsa_key_pem:
                self.rsa_private_key = deserialize_private_key(rsa_key_pem.encode('utf-8'))
            
            # Load EC private key
            ec_key_pem = keys_data.get('ec_private_key')
            if ec_key_pem:
                self.ec_private_key = deserialize_private_key(ec_key_pem.encode('utf-8'))
                
        except Exception as e:
            print(f"Error loading keys: {e}")
            self.rsa_private_key = None
            self.ec_private_key = None
    
    def _generate_keys_and_cert(self):
        """Generate new keys and certificate"""
        # Generate RSA key pair for signing
        self.rsa_private_key, _ = generate_rsa_keypair(RSA_KEY_SIZE)
        
        # Generate EC key pair for ECDH
        self.ec_private_key, _ = generate_ec_keypair()
        
        # Create self-signed certificate
        self.certificate = create_self_signed_certificate(
            self.user_id,
            self.user_name,
            self.rsa_private_key,
            CERT_VALIDITY_DAYS
        )
        
        # Save keys and certificate
        self._save_keys()
    
    def _save_keys(self):
        """Save keys and certificate to disk"""
        keys_data = {
            'rsa_private_key': serialize_private_key(self.rsa_private_key).decode('utf-8'),
            'ec_private_key': serialize_private_key(self.ec_private_key).decode('utf-8'),
            'certificate': self.certificate
        }
        
        with open(self.keys_file, 'w', encoding='utf-8') as f:
            json.dump(keys_data, f, indent=2)
    
    def has_profile(self) -> bool:
        """Check if profile exists"""
        return self.user_id is not None
    
    def create_account(self, user_name: str) -> bool:
        """Create a new user account"""
        try:
            self.user_id = str(uuid.uuid4())
            self.user_name = user_name
            self.created_at = datetime.utcnow().isoformat()
            
            # Generate keys and certificate
            self._generate_keys_and_cert()
            
            # Save profile
            self._save_profile()
            
            return True
        except Exception as e:
            print(f"Error creating account: {e}")
            return False
    
    def _save_profile(self):
        """Save profile to disk"""
        profile_data = {
            'user_id': self.user_id,
            'user_name': self.user_name,
            'avatar_path': self.avatar_path,
            'created_at': self.created_at
        }
        
        with open(self.profile_file, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2)
    
    def update_name(self, new_name: str) -> bool:
        """Update user name"""
        try:
            self.user_name = new_name
            
            # Regenerate certificate with new name
            self.certificate = create_self_signed_certificate(
                self.user_id,
                self.user_name,
                self.rsa_private_key,
                CERT_VALIDITY_DAYS
            )
            
            self._save_profile()
            self._save_keys()
            
            return True
        except Exception as e:
            print(f"Error updating name: {e}")
            return False
    
    def get_user_id(self) -> Optional[str]:
        """Get user ID"""
        return self.user_id
    
    def get_user_name(self) -> Optional[str]:
        """Get user name"""
        return self.user_name
    
    def get_certificate(self) -> Optional[Dict[str, Any]]:
        """Get user certificate"""
        return self.certificate
    
    def get_certificate_fingerprint(self) -> Optional[str]:
        """Get certificate fingerprint"""
        if self.certificate:
            return self.certificate.get('fingerprint')
        return None
    
    def get_rsa_private_key(self):
        """Get RSA private key"""
        return self.rsa_private_key
    
    def get_ec_private_key(self):
        """Get EC private key"""
        return self.ec_private_key
    
    def set_avatar_path(self, path: str):
        """Set avatar path"""
        self.avatar_path = path
        self._save_profile()
