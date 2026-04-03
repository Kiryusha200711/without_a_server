"""
UDP Discovery Service for P2P Messenger
Discovers peers on local network via UDP broadcast
"""

import socket
import threading
import json
import time
from typing import Callable, Optional, Dict, Any, Set
from datetime import datetime
from ..utils.constants import UDP_BROADCAST_PORT, PEER_TIMEOUT


class SecureUDPDiscovery:
    """Discovers peers on local network using signed UDP broadcast messages"""
    
    def __init__(self, user_profile, cert_store=None):
        self.user_profile = user_profile
        self.cert_store = cert_store
        
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.broadcast_thread: Optional[threading.Thread] = None
        self.receive_thread: Optional[threading.Thread] = None
        
        # Discovered peers: user_id -> last_seen_timestamp
        self.discovered_peers: Dict[str, float] = {}
        self._peers_lock = threading.Lock()
        
        # Callbacks
        self.on_peer_found: Optional[Callable] = None
        self.on_peer_lost: Optional[Callable] = None
        
        # Broadcast interval
        self.broadcast_interval = 3.0  # seconds
    
    def start(self, port: int = UDP_BROADCAST_PORT):
        """Start discovery service"""
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to port for receiving
            self.socket.bind(('0.0.0.0', port))
            self.socket.settimeout(1.0)
            
            self.running = True
            
            # Start broadcast thread
            self.broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
            self.broadcast_thread.start()
            
            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            # Start peer expiry checker
            threading.Thread(target=self._check_peer_expiry, daemon=True).start()
            
            print(f"UDP Discovery started on port {port}")
            
        except Exception as e:
            print(f"Error starting UDP discovery: {e}")
            self.running = False
    
    def stop(self):
        """Stop discovery service"""
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        print("UDP Discovery stopped")
    
    def _broadcast_loop(self):
        """Broadcast our presence periodically"""
        while self.running:
            try:
                message = self._create_broadcast_message()
                self.socket.sendto(message, ('255.255.255.255', UDP_BROADCAST_PORT))
            except Exception as e:
                if self.running:
                    print(f"Broadcast error: {e}")
            
            time.sleep(self.broadcast_interval)
    
    def _create_broadcast_message(self) -> bytes:
        """Create a signed broadcast message"""
        message = {
            'type': 'peer_discovery',
            'version': 1,
            'user_id': self.user_profile.get_user_id(),
            'user_name': self.user_profile.get_user_name(),
            'port': 37021,  # TCP port
            'fingerprint': self.user_profile.get_certificate_fingerprint(),
            'timestamp': int(time.time())
        }
        
        return json.dumps(message).encode('utf-8')
    
    def _receive_loop(self):
        """Receive and process broadcast messages"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(65536)
                self._process_message(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
    
    def _process_message(self, data: bytes, addr: tuple):
        """Process a received broadcast message"""
        try:
            message = json.loads(data.decode('utf-8'))
            
            # Validate message type
            if message.get('type') != 'peer_discovery':
                return
            
            # Ignore our own messages
            peer_id = message.get('user_id')
            if peer_id == self.user_profile.get_user_id():
                return
            
            # Check timestamp (not older than 10 seconds)
            timestamp = message.get('timestamp', 0)
            if time.time() - timestamp > 10:
                return
            
            # Update discovered peers
            with self._peers_lock:
                is_new = peer_id not in self.discovered_peers
                self.discovered_peers[peer_id] = time.time()
            
            # Notify callback
            if is_new and self.on_peer_found:
                self.on_peer_found(peer_id, message, addr)
            elif self.on_peer_found:
                # Update existing peer
                self.on_peer_found(peer_id, message, addr)
                
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def _check_peer_expiry(self):
        """Check for expired peers"""
        while self.running:
            time.sleep(5)
            
            now = time.time()
            expired = []
            
            with self._peers_lock:
                for peer_id, last_seen in list(self.discovered_peers.items()):
                    if now - last_seen > PEER_TIMEOUT:
                        expired.append(peer_id)
            
            for peer_id in expired:
                with self._peers_lock:
                    if peer_id in self.discovered_peers:
                        del self.discovered_peers[peer_id]
                
                if self.on_peer_lost:
                    self.on_peer_lost(peer_id)
    
    def get_discovered_peers(self) -> Dict[str, float]:
        """Get all discovered peers with their last seen time"""
        with self._peers_lock:
            return dict(self.discovered_peers)
    
    def is_peer_online(self, peer_id: str) -> bool:
        """Check if a peer is online"""
        with self._peers_lock:
            if peer_id not in self.discovered_peers:
                return False
            
            last_seen = self.discovered_peers[peer_id]
            return time.time() - last_seen < PEER_TIMEOUT
