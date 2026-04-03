"""
Certificate Store for P2P Messenger
Stores and manages peer certificates with trust verification
"""

import json
import os
from typing import Dict, Optional, Tuple, List
from datetime import datetime
from .crypto_utils import verify_certificate, compute_fingerprint


class CertificateStore:
    """Manages storage and verification of peer certificates"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.cert_file = os.path.join(data_dir, 'certificates.json')
        self.trust_file = os.path.join(data_dir, 'trusted_fingerprints.json')
        self.certs: Dict[str, dict] = {}  # user_id -> cert_data
        self.trusted_fingerprints: set = set()
        self._load()
    
    def _load(self):
        """Load certificates and trusted fingerprints from disk"""
        # Load certificates
        if os.path.exists(self.cert_file):
            try:
                with open(self.cert_file, 'r', encoding='utf-8') as f:
                    self.certs = json.load(f)
            except Exception as e:
                print(f"Error loading certificates: {e}")
                self.certs = {}
        
        # Load trusted fingerprints
        if os.path.exists(self.trust_file):
            try:
                with open(self.trust_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.trusted_fingerprints = set(data.get('fingerprints', []))
            except Exception as e:
                print(f"Error loading trusted fingerprints: {e}")
                self.trusted_fingerprints = set()
    
    def _save(self):
        """Save certificates and trusted fingerprints to disk"""
        try:
            with open(self.cert_file, 'w', encoding='utf-8') as f:
                json.dump(self.certs, f, indent=2)
            
            with open(self.trust_file, 'w', encoding='utf-8') as f:
                json.dump({'fingerprints': list(self.trusted_fingerprints)}, f, indent=2)
        except Exception as e:
            print(f"Error saving certificates: {e}")
    
    def add_certificate(self, user_id: str, cert_data: dict, trust: bool = False) -> bool:
        """Add or update a certificate"""
        try:
            # Verify the certificate first
            is_valid, msg = verify_certificate(cert_data)
            if not is_valid:
                print(f"Invalid certificate for {user_id}: {msg}")
                return False
            
            # Check fingerprint matches
            computed_fp = compute_fingerprint(
                json.dumps({k: v for k, v in cert_data.items() if k != 'fingerprint'}, sort_keys=True).encode('utf-8')
            )
            if computed_fp != cert_data.get('fingerprint'):
                print("Fingerprint mismatch")
                return False
            
            self.certs[user_id] = cert_data
            
            if trust:
                self.trusted_fingerprints.add(cert_data['fingerprint'])
            
            self._save()
            return True
        except Exception as e:
            print(f"Error adding certificate: {e}")
            return False
    
    def get_certificate(self, user_id: str) -> Optional[dict]:
        """Get certificate for a user"""
        return self.certs.get(user_id)
    
    def has_certificate(self, user_id: str) -> bool:
        """Check if we have a certificate for a user"""
        return user_id in self.certs
    
    def trust_certificate(self, user_id: str) -> bool:
        """Mark a certificate as trusted"""
        cert = self.certs.get(user_id)
        if cert:
            self.trusted_fingerprints.add(cert['fingerprint'])
            self._save()
            return True
        return False
    
    def is_trusted(self, user_id: str) -> bool:
        """Check if a certificate is trusted"""
        cert = self.certs.get(user_id)
        if cert:
            return cert['fingerprint'] in self.trusted_fingerprints
        return False
    
    def verify_certificate(self, cert_data: dict) -> Tuple[bool, str]:
        """
        Verify a certificate against stored ones
        Returns (is_valid, message)
        """
        # First verify the certificate itself
        is_valid, msg = verify_certificate(cert_data)
        if not is_valid:
            return False, msg
        
        user_id = cert_data.get('user_id')
        fingerprint = cert_data.get('fingerprint')
        
        # Check if we have a stored certificate for this user
        stored_cert = self.certs.get(user_id)
        if stored_cert:
            # Compare fingerprints - if different, possible MITM attack
            if stored_cert['fingerprint'] != fingerprint:
                return False, "Certificate changed! Possible MITM attack."
            
            # Check if trusted
            if fingerprint in self.trusted_fingerprints:
                return True, "Trusted certificate"
            else:
                return False, "Known but not trusted"
        else:
            # New certificate
            if fingerprint in self.trusted_fingerprints:
                return True, "Trusted fingerprint (new certificate)"
            else:
                return False, "Unknown certificate"
    
    def remove_certificate(self, user_id: str) -> bool:
        """Remove a certificate"""
        if user_id in self.certs:
            cert = self.certs[user_id]
            self.trusted_fingerprints.discard(cert['fingerprint'])
            del self.certs[user_id]
            self._save()
            return True
        return False
    
    def get_all_certificates(self) -> List[dict]:
        """Get all stored certificates"""
        return list(self.certs.values())
    
    def get_trusted_count(self) -> int:
        """Get count of trusted certificates"""
        return len(self.trusted_fingerprints)
