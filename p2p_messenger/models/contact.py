"""
Contact Model for P2P Messenger
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from ..utils.constants import CONTACT_OFFLINE


class ContactAddress:
    """Represents a single address (IP:port) for a contact"""
    
    def __init__(self, ip: str, port: int, addr_type: str = 'ipv4', priority: int = 50):
        self.ip = ip
        self.port = port
        self.addr_type = addr_type  # 'ipv4', 'ipv6', 'hostname'
        self.priority = priority
        self.last_seen: Optional[float] = None
        self.last_success: Optional[float] = None
        self.fail_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            'ip': self.ip,
            'port': self.port,
            'addr_type': self.addr_type,
            'priority': self.priority,
            'last_seen': self.last_seen,
            'last_success': self.last_success,
            'fail_count': self.fail_count
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ContactAddress':
        addr = cls(
            data['ip'],
            data['port'],
            data.get('addr_type', 'ipv4'),
            data.get('priority', 50)
        )
        addr.last_seen = data.get('last_seen')
        addr.last_success = data.get('last_success')
        addr.fail_count = data.get('fail_count', 0)
        return addr
    
    def is_reliable(self) -> bool:
        """Check if this address is reliable"""
        now = datetime.utcnow().timestamp()
        # Reliable if successful in last 5 minutes or fail count < 3
        if self.last_success and (now - self.last_success) < 300:
            return True
        return self.fail_count < 3
    
    def effective_priority(self) -> int:
        """Calculate effective priority (lower is better)"""
        base = self.priority
        if self.last_success:
            base -= 5  # Bonus for recent success
        base += self.fail_count * 10  # Penalty for failures
        return base
    
    def mark_success(self):
        """Mark this address as successfully used"""
        self.last_success = datetime.utcnow().timestamp()
        self.fail_count = 0
    
    def mark_failure(self):
        """Mark this address as failed"""
        self.fail_count += 1


class AddressBook:
    """Manages multiple addresses for a single contact"""
    
    def __init__(self):
        self.addresses: List[ContactAddress] = []
    
    def add_address(self, ip: str, port: int, addr_type: str = 'ipv4', priority: int = 50) -> bool:
        """Add or update an address"""
        # Check if already exists
        for addr in self.addresses:
            if addr.ip == ip and addr.port == port:
                addr.last_seen = datetime.utcnow().timestamp()
                return False
        
        # Add new address
        addr = ContactAddress(ip, port, addr_type, priority)
        addr.last_seen = datetime.utcnow().timestamp()
        self.addresses.append(addr)
        return True
    
    def get_best_address(self) -> Optional[ContactAddress]:
        """Get the best available address"""
        reliable_addrs = [a for a in self.addresses if a.is_reliable()]
        if not reliable_addrs:
            reliable_addrs = self.addresses
        
        if not reliable_addrs:
            return None
        
        return min(reliable_addrs, key=lambda a: a.effective_priority())
    
    def get_all_addresses(self) -> List[ContactAddress]:
        """Get all addresses sorted by priority"""
        return sorted(self.addresses, key=lambda a: a.effective_priority())
    
    def remove_address(self, ip: str, port: int) -> bool:
        """Remove an address"""
        for i, addr in enumerate(self.addresses):
            if addr.ip == ip and addr.port == port:
                del self.addresses[i]
                return True
        return False
    
    def to_dict(self) -> dict:
        return {
            'addresses': [addr.to_dict() for addr in self.addresses]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AddressBook':
        book = cls()
        for addr_data in data.get('addresses', []):
            book.addresses.append(ContactAddress.from_dict(addr_data))
        return book


class Contact:
    """Represents a peer contact"""
    
    def __init__(self, contact_id: str, name: str, host: str = None, port: int = None):
        self.contact_id = contact_id
        self.name = name
        self.status = CONTACT_OFFLINE
        self.last_seen: Optional[float] = None
        self.avatar_path: Optional[str] = None
        self.transports_info: Dict[str, Any] = {}
        self.cert_fingerprint: Optional[str] = None
        self.address_book = AddressBook()
        
        # Add initial address if provided
        if host and port:
            addr_type = 'ipv6' if ':' in host else 'hostname' if not host.replace('.', '').isdigit() else 'ipv4'
            self.address_book.add_address(host, port, addr_type)
    
    def to_dict(self) -> dict:
        return {
            'contact_id': self.contact_id,
            'name': self.name,
            'status': self.status,
            'last_seen': self.last_seen,
            'avatar_path': self.avatar_path,
            'transports_info': self.transports_info,
            'cert_fingerprint': self.cert_fingerprint,
            'address_book': self.address_book.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Contact':
        contact = cls(
            data['contact_id'],
            data['name']
        )
        contact.status = data.get('status', CONTACT_OFFLINE)
        contact.last_seen = data.get('last_seen')
        contact.avatar_path = data.get('avatar_path')
        contact.transports_info = data.get('transports_info', {})
        contact.cert_fingerprint = data.get('cert_fingerprint')
        
        if 'address_book' in data:
            contact.address_book = AddressBook.from_dict(data['address_book'])
        
        return contact
    
    def update_status(self, status: int):
        """Update contact status"""
        self.status = status
        if status != CONTACT_OFFLINE:
            self.last_seen = datetime.utcnow().timestamp()
    
    def is_online(self) -> bool:
        """Check if contact is online"""
        return self.status != CONTACT_OFFLINE
    
    def add_address(self, ip: str, port: int, addr_type: str = 'ipv4', priority: int = 50):
        """Add an address to this contact"""
        self.address_book.add_address(ip, port, addr_type, priority)
    
    def get_best_address(self) -> Optional[ContactAddress]:
        """Get the best address for this contact"""
        return self.address_book.get_best_address()
