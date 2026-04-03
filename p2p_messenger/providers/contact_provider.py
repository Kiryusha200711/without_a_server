"""
Contact Provider for P2P Messenger
Manages contacts, discovery, and connections
"""

import threading
from typing import Dict, Optional, Callable, List
from datetime import datetime

from ..models.contact import Contact
from ..models.user_profile import UserProfile
from ..core.database_helper import DatabaseHelper
from ..security.cert_store import CertificateStore
from ..services.udp_discovery import SecureUDPDiscovery
from ..transports.secure_tcp_transport import SecureTCPTransport


class ContactProvider:
    """Main coordinator for contacts and connections"""
    
    def __init__(self, user_profile: UserProfile, cert_store: CertificateStore,
                 db_helper: DatabaseHelper, data_dir: str):
        self.user_profile = user_profile
        self.cert_store = cert_store
        self.db_helper = db_helper
        self.data_dir = data_dir
        
        # Contacts storage
        self.contacts: Dict[str, Contact] = {}
        
        # Active transports
        self.active_transports: Dict[str, SecureTCPTransport] = {}
        
        # Chat providers registry
        self.chat_providers: Dict[str, any] = {}
        
        # UDP Discovery
        self.udp_discovery: Optional[SecureUDPDiscovery] = None
        
        # TCP Server (will be implemented)
        self.tcp_server = None
        
        # Callbacks
        self.on_contact_added: Optional[Callable] = None
        self.on_contact_removed: Optional[Callable] = None
        self.on_contact_updated: Optional[Callable] = None
        
        # Load contacts from database
        self._load_contacts()
    
    def _load_contacts(self):
        """Load contacts from database"""
        contacts_data = self.db_helper.get_all_contacts()
        for contact_data in contacts_data:
            contact = Contact.from_dict(contact_data)
            self.contacts[contact.contact_id] = contact
    
    def start(self):
        """Start all services"""
        # Start UDP discovery
        self.udp_discovery = SecureUDPDiscovery(self.user_profile, self.cert_store)
        self.udp_discovery.on_peer_found = self._on_peer_found
        self.udp_discovery.on_peer_lost = self._on_peer_lost
        self.udp_discovery.start()
        
        # Start TCP server (simplified - will listen on all interfaces)
        self._start_tcp_server()
        
        print("ContactProvider started")
    
    def stop(self):
        """Stop all services"""
        if self.udp_discovery:
            self.udp_discovery.stop()
        
        # Close all transports
        for transport in list(self.active_transports.values()):
            transport.disconnect()
        self.active_transports.clear()
        
        print("ContactProvider stopped")
    
    def _start_tcp_server(self):
        """Start TCP server to accept incoming connections"""
        import socket
        import threading
        
        def server_loop():
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                server_socket.bind(('0.0.0.0', 37021))
                server_socket.listen(5)
                server_socket.settimeout(1.0)
                
                print("TCP Server listening on port 37021")
                
                while True:
                    try:
                        client_socket, addr = server_socket.accept()
                        self._handle_incoming_connection(client_socket, addr)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if hasattr(self, '_server_running') and self._server_running:
                            print(f"Server error: {e}")
                        break
            except Exception as e:
                print(f"Failed to start TCP server: {e}")
            finally:
                server_socket.close()
        
        self._server_running = True
        thread = threading.Thread(target=server_loop, daemon=True)
        thread.start()
    
    def _handle_incoming_connection(self, client_socket, addr):
        """Handle incoming TCP connection"""
        try:
            transport = SecureTCPTransport(
                self.user_profile,
                self.cert_store,
                is_server=True
            )
            
            # Setup callbacks
            transport.on_disconnected = lambda peer_id: self._on_transport_disconnected(peer_id)
            
            if transport.accept_connection(client_socket):
                peer_id = transport.peer_user_id
                
                # Store transport
                self.active_transports[peer_id] = transport
                
                # Update or create contact
                if peer_id not in self.contacts:
                    contact = Contact(peer_id, transport.peer_name or "Unknown")
                    contact.update_status(1)  # ONLINE
                    contact.cert_fingerprint = transport._peer_cert.get('fingerprint') if transport._peer_cert else None
                    self.contacts[peer_id] = contact
                    self.db_helper.add_or_update_contact(contact)
                    
                    if self.on_contact_added:
                        self.on_contact_added(contact)
                else:
                    self.contacts[peer_id].update_status(1)
                    self.db_helper.update_contact_status(peer_id, 1)
                    
                    if self.on_contact_updated:
                        self.on_contact_updated(self.contacts[peer_id])
                
                # Route incoming messages to chat provider
                transport.on_text = lambda msg_id, text: self._route_message(peer_id, 'text', msg_id, text)
                transport.on_typing = lambda is_typing: self._route_typing(peer_id, is_typing)
                
                print(f"Accepted connection from {peer_id}")
        except Exception as e:
            print(f"Error handling incoming connection: {e}")
            client_socket.close()
    
    def _route_message(self, peer_id: str, msg_type: str, *args):
        """Route incoming message to chat provider"""
        if peer_id in self.chat_providers:
            chat_provider = self.chat_providers[peer_id]
            if msg_type == 'text':
                chat_provider.on_text_received(*args)
    
    def _route_typing(self, peer_id: str, is_typing: bool):
        """Route typing indicator to chat provider"""
        if peer_id in self.chat_providers:
            chat_provider = self.chat_providers[peer_id]
            chat_provider.on_typing_received(is_typing)
    
    def _on_peer_found(self, peer_id: str, message: dict, addr: tuple):
        """Handle peer discovered via UDP"""
        # Update or create contact
        if peer_id not in self.contacts:
            contact = Contact(peer_id, message.get('user_name', 'Unknown'))
            contact.update_status(1)  # ONLINE
            contact.cert_fingerprint = message.get('fingerprint')
            
            # Add address from UDP discovery
            contact.add_address(addr[0], message.get('port', 37021), 'ipv4', priority=30)
            
            self.contacts[peer_id] = contact
            self.db_helper.add_or_update_contact(contact)
            
            if self.on_contact_added:
                self.on_contact_added(contact)
        else:
            # Update existing contact
            contact = self.contacts[peer_id]
            contact.update_status(1)
            contact.add_address(addr[0], message.get('port', 37021), 'ipv4', priority=30)
            
            self.db_helper.add_or_update_contact(contact)
            
            if self.on_contact_updated:
                self.on_contact_updated(contact)
    
    def _on_peer_lost(self, peer_id: str):
        """Handle peer lost from UDP discovery"""
        if peer_id in self.contacts:
            # Only mark offline if no active TCP connection
            if peer_id not in self.active_transports:
                self.contacts[peer_id].update_status(0)  # OFFLINE
                self.db_helper.update_contact_status(peer_id, 0)
                
                if self.on_contact_updated:
                    self.on_contact_updated(self.contacts[peer_id])
    
    def _on_transport_disconnected(self, peer_id: str):
        """Handle transport disconnection"""
        if peer_id in self.active_transports:
            del self.active_transports[peer_id]
    
    def add_contact_manual(self, name: str, host: str, port: int) -> Optional[Contact]:
        """Add a contact manually by IP/hostname"""
        import uuid
        
        contact_id = str(uuid.uuid4())
        contact = Contact(contact_id, name, host, port)
        
        self.contacts[contact_id] = contact
        self.db_helper.add_or_update_contact(contact)
        
        if self.on_contact_added:
            self.on_contact_added(contact)
        
        return contact
    
    def remove_contact(self, contact_id: str) -> bool:
        """Remove a contact"""
        if contact_id not in self.contacts:
            return False
        
        # Close transport if exists
        if contact_id in self.active_transports:
            self.active_transports[contact_id].disconnect()
            del self.active_transports[contact_id]
        
        # Remove from database
        self.db_helper.delete_contact(contact_id)
        
        # Remove from memory
        del self.contacts[contact_id]
        
        if self.on_contact_removed:
            self.on_contact_removed(contact_id)
        
        return True
    
    def get_contact(self, contact_id: str) -> Optional[Contact]:
        """Get a contact by ID"""
        return self.contacts.get(contact_id)
    
    def get_all_contacts(self) -> List[Contact]:
        """Get all contacts"""
        return list(self.contacts.values())
    
    def connect_to_contact(self, contact_id: str) -> bool:
        """Connect to a contact"""
        contact = self.contacts.get(contact_id)
        if not contact:
            return False
        
        # Check if already connected
        if contact_id in self.active_transports:
            return True
        
        # Get best address
        addr = contact.address_book.get_best_address()
        if not addr:
            return False
        
        # Create transport and connect
        transport = SecureTCPTransport(self.user_profile, self.cert_store)
        
        # Setup callbacks
        transport.on_disconnected = lambda peer_id: self._on_transport_disconnected(peer_id)
        
        if transport.connect(addr.ip, addr.port):
            self.active_transports[contact_id] = transport
            
            # Update contact status
            contact.update_status(1)
            self.db_helper.update_contact_status(contact_id, 1)
            
            # Setup message routing
            transport.on_text = lambda msg_id, text: self._route_message(contact_id, 'text', msg_id, text)
            transport.on_typing = lambda is_typing: self._route_typing(contact_id, is_typing)
            
            return True
        
        return False
    
    def get_transport(self, contact_id: str) -> Optional[SecureTCPTransport]:
        """Get transport for a contact"""
        return self.active_transports.get(contact_id)
    
    def create_chat_provider(self, contact_id: str):
        """Create a chat provider for a contact"""
        from .chat_provider import ChatProvider
        
        chat_provider = ChatProvider(contact_id, self)
        self.chat_providers[contact_id] = chat_provider
        return chat_provider
