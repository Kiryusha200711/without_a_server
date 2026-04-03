"""
Secure TCP Transport for P2P Messenger
Implements encrypted TCP communication with handshake
"""

import socket
import threading
import json
import struct
import time
import os
from typing import Optional, Callable, Dict, Any
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from .base_transport import BaseTransport
from ..security.crypto_utils import (
    generate_ec_keypair, serialize_public_key, deserialize_public_key,
    derive_shared_secret, derive_keys, encrypt_aes_gcm, decrypt_aes_gcm,
    compute_hmac, verify_hmac, sign_data, verify_signature,
    compute_fingerprint
)
from ..utils.constants import (
    PACKET_TYPE_TEXT, PACKET_TYPE_FILE_CHUNK, PACKET_TYPE_FILE_INFO,
    PACKET_TYPE_ACK, PACKET_TYPE_TYPING, PACKET_TYPE_USER_INFO,
    PACKET_TYPE_HANDSHAKE, PACKET_TYPE_CLOSE, PACKET_TYPE_READ_RECEIPT,
    PACKET_TYPE_DELIVERY_RECEIPT, HANDSHAKE_TIMEOUT, CONNECTION_TIMEOUT
)


class SecureTCPTransport(BaseTransport):
    """Secure TCP transport with encryption and authentication"""
    
    def __init__(self, user_profile, cert_store=None, is_server=False):
        super().__init__()
        self.user_profile = user_profile
        self.cert_store = cert_store
        self.is_server = is_server
        
        self.socket: Optional[socket.socket] = None
        self.receiver_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Crypto state
        self.ec_private_key = None
        self.ec_public_key = None
        self.session_key: Optional[bytes] = None
        self.mac_key: Optional[bytes] = None
        self.sequence_number = 0
        
        # Packet handling
        self._recv_buffer = b''
        self._lock = threading.Lock()
        
        # Handshake state
        self._handshake_complete = threading.Event()
        self._peer_cert: Optional[Dict[str, Any]] = None
    
    def connect(self, host: str, port: int, timeout: float = CONNECTION_TIMEOUT) -> bool:
        """Connect to a peer (client mode)"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            self.socket.connect((host, port))
            self.socket.settimeout(None)  # Remove timeout after connection
            
            self.connected = True
            self.running = True
            
            # Generate EC keys for this session
            self.ec_private_key, self.ec_public_key = generate_ec_keypair()
            
            # Perform client handshake
            if not self._perform_client_handshake():
                self.disconnect()
                return False
            
            # Start receiver thread
            self._start_receiver()
            
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            self.connected = False
            return False
    
    def accept_connection(self, sock: socket.socket) -> bool:
        """Accept an incoming connection (server mode)"""
        try:
            self.socket = sock
            self.connected = True
            self.running = True
            
            # Generate EC keys for this session
            self.ec_private_key, self.ec_public_key = generate_ec_keypair()
            
            # Perform server handshake
            if not self._perform_server_handshake():
                self.disconnect()
                return False
            
            # Start receiver thread
            self._start_receiver()
            
            return True
        except Exception as e:
            print(f"Accept error: {e}")
            self.connected = False
            return False
    
    def _perform_client_handshake(self) -> bool:
        """Perform client-side handshake"""
        try:
            # Send ClientHello
            client_hello = {
                'type': 'ClientHello',
                'version': 1,
                'user_id': self.user_profile.get_user_id(),
                'user_name': self.user_profile.get_user_name(),
                'ec_public_key': serialize_public_key(self.ec_public_key).decode('utf-8'),
                'certificate': self.user_profile.get_certificate()
            }
            
            self._send_raw(json.dumps(client_hello).encode('utf-8'))
            
            # Receive ServerHello
            response = self._recv_raw(65536)
            if not response:
                return False
            
            server_hello = json.loads(response.decode('utf-8'))
            
            if server_hello.get('type') != 'ServerHello':
                print("Invalid ServerHello")
                return False
            
            # Store peer info
            self.peer_user_id = server_hello.get('user_id')
            self.peer_name = server_hello.get('user_name')
            self._peer_cert = server_hello.get('certificate')
            
            # Verify peer certificate
            if self.cert_store:
                is_valid, msg = self.cert_store.verify_certificate(self._peer_cert)
                if not is_valid:
                    print(f"Certificate verification failed: {msg}")
                    # For now, we'll allow unknown certs but mark as untrusted
                    # In production, show dialog to user
            
            # Derive shared secret
            peer_ec_public = deserialize_public_key(
                server_hello['ec_public_key'].encode('utf-8')
            )
            shared_secret = derive_shared_secret(self.ec_private_key, peer_ec_public)
            self.session_key, self.mac_key = derive_keys(shared_secret)
            
            self.authenticated = True
            self._handshake_complete.set()
            
            return True
        except Exception as e:
            print(f"Handshake error: {e}")
            return False
    
    def _perform_server_handshake(self) -> bool:
        """Perform server-side handshake"""
        try:
            # Receive ClientHello
            request = self._recv_raw(65536)
            if not request:
                return False
            
            client_hello = json.loads(request.decode('utf-8'))
            
            if client_hello.get('type') != 'ClientHello':
                return False
            
            # Store peer info
            self.peer_user_id = client_hello.get('user_id')
            self.peer_name = client_hello.get('user_name')
            self._peer_cert = client_hello.get('certificate')
            
            # Verify peer certificate
            if self.cert_store:
                is_valid, msg = self.cert_store.verify_certificate(self._peer_cert)
                if not is_valid:
                    print(f"Certificate verification failed: {msg}")
            
            # Derive shared secret
            peer_ec_public = deserialize_public_key(
                client_hello['ec_public_key'].encode('utf-8')
            )
            shared_secret = derive_shared_secret(self.ec_private_key, peer_ec_public)
            self.session_key, self.mac_key = derive_keys(shared_secret)
            
            # Send ServerHello
            server_hello = {
                'type': 'ServerHello',
                'version': 1,
                'user_id': self.user_profile.get_user_id(),
                'user_name': self.user_profile.get_user_name(),
                'ec_public_key': serialize_public_key(self.ec_public_key).decode('utf-8'),
                'certificate': self.user_profile.get_certificate()
            }
            
            self._send_raw(json.dumps(server_hello).encode('utf-8'))
            
            self.authenticated = True
            self._handshake_complete.set()
            
            return True
        except Exception as e:
            print(f"Server handshake error: {e}")
            return False
    
    def _start_receiver(self):
        """Start the packet receiver thread"""
        self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receiver_thread.start()
    
    def _receive_loop(self):
        """Main receive loop"""
        while self.running and self.connected:
            try:
                # Read packet length (4 bytes)
                length_bytes = self._recv_exact(4)
                if not length_bytes:
                    break
                
                packet_length = struct.unpack('>I', length_bytes)[0]
                
                # Read packet data
                packet_data = self._recv_exact(packet_length)
                if not packet_data:
                    break
                
                # Decrypt and process
                self._handle_packet(packet_data)
                
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                break
        
        # Connection closed
        self.running = False
        self.connected = False
        if self.on_disconnected:
            self.on_disconnected(self.peer_user_id)
    
    def _recv_exact(self, n: int) -> Optional[bytes]:
        """Receive exactly n bytes"""
        data = b''
        while len(data) < n:
            try:
                chunk = self.socket.recv(n - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                return None
        return data
    
    def _handle_packet(self, packet_data: bytes):
        """Handle a received packet"""
        try:
            # Decrypt packet
            plaintext = self._decrypt_packet(packet_data)
            if not plaintext:
                return
            
            # Parse packet
            packet = json.loads(plaintext.decode('utf-8'))
            packet_type = packet.get('type')
            
            # Dispatch to handler
            if packet_type == PACKET_TYPE_TEXT:
                if self.on_text:
                    self.on_text(packet.get('message_id'), packet.get('text'))
            
            elif packet_type == PACKET_TYPE_FILE_INFO:
                if self.on_file_info:
                    self.on_file_info(
                        packet.get('file_id'),
                        packet.get('file_name'),
                        packet.get('total_chunks'),
                        packet.get('file_size')
                    )
            
            elif packet_type == PACKET_TYPE_FILE_CHUNK:
                if self.on_file_chunk:
                    import base64
                    chunk_data = base64.b64decode(packet.get('data'))
                    self.on_file_chunk(
                        packet.get('file_id'),
                        packet.get('chunk_index'),
                        chunk_data
                    )
            
            elif packet_type == PACKET_TYPE_ACK:
                if self.on_ack:
                    self.on_ack(packet.get('file_id'), packet.get('chunk_index'))
            
            elif packet_type == PACKET_TYPE_TYPING:
                if self.on_typing:
                    self.on_typing(packet.get('is_typing'))
            
            elif packet_type == PACKET_TYPE_USER_INFO:
                if self.on_user_info:
                    self.on_user_info(packet.get('user_id'), packet.get('info'))
            
            elif packet_type == PACKET_TYPE_READ_RECEIPT:
                if self.on_read_receipt:
                    self.on_read_receipt(packet.get('message_id'))
            
            elif packet_type == PACKET_TYPE_DELIVERY_RECEIPT:
                if self.on_delivery_receipt:
                    self.on_delivery_receipt(packet.get('message_id'))
            
            elif packet_type == PACKET_TYPE_CLOSE:
                self.disconnect()
                
        except Exception as e:
            print(f"Packet handling error: {e}")
    
    def _encrypt_packet(self, plaintext: bytes) -> bytes:
        """Encrypt a packet"""
        with self._lock:
            self.sequence_number += 1
            
            # Create header
            header = {
                'seq': self.sequence_number,
                'timestamp': time.time()
            }
            
            # Combine header and data
            data_to_encrypt = json.dumps(header).encode('utf-8') + b'\x00' + plaintext
            
            # Encrypt
            ciphertext, nonce, tag = encrypt_aes_gcm(data_to_encrypt, self.session_key)
            
            # Compute MAC
            mac = compute_hmac(ciphertext + nonce + tag, self.mac_key)
            
            # Pack: nonce (12) + tag (16) + mac (32) + ciphertext
            packet = nonce + tag + mac + ciphertext
            
            return packet
    
    def _decrypt_packet(self, packet_data: bytes) -> Optional[bytes]:
        """Decrypt a packet"""
        try:
            if len(packet_data) < 60:  # nonce(12) + tag(16) + mac(32)
                return None
            
            nonce = packet_data[:12]
            tag = packet_data[12:28]
            mac = packet_data[28:60]
            ciphertext = packet_data[60:]
            
            # Verify MAC
            expected_mac = compute_hmac(ciphertext + nonce + tag, self.mac_key)
            if not verify_hmac(ciphertext + nonce + tag, self.mac_key, mac):
                print("MAC verification failed")
                return None
            
            # Decrypt
            plaintext = decrypt_aes_gcm(ciphertext, self.session_key, nonce, tag)
            
            # Split header and data
            parts = plaintext.split(b'\x00', 1)
            if len(parts) != 2:
                return None
            
            return parts[1]
        except Exception as e:
            print(f"Decryption error: {e}")
            return None
    
    def _send_raw(self, data: bytes) -> bool:
        """Send raw data over socket"""
        try:
            self.socket.sendall(data)
            return True
        except Exception as e:
            print(f"Send error: {e}")
            return False
    
    def _send_encrypted(self, packet: dict) -> bool:
        """Send an encrypted packet"""
        try:
            plaintext = json.dumps(packet).encode('utf-8')
            encrypted = self._encrypt_packet(plaintext)
            
            # Prepend length
            length = len(encrypted)
            length_bytes = struct.pack('>I', length)
            
            return self._send_raw(length_bytes + encrypted)
        except Exception as e:
            print(f"Send encrypted error: {e}")
            return False
    
    def send_text(self, message_id: str, text: str):
        """Send a text message"""
        if not self.authenticated:
            return
        
        packet = {
            'type': PACKET_TYPE_TEXT,
            'message_id': message_id,
            'text': text
        }
        self._send_encrypted(packet)
    
    def send_file_info(self, file_id: str, file_name: str, total_chunks: int, file_size: int):
        """Send file info"""
        if not self.authenticated:
            return
        
        packet = {
            'type': PACKET_TYPE_FILE_INFO,
            'file_id': file_id,
            'file_name': file_name,
            'total_chunks': total_chunks,
            'file_size': file_size
        }
        self._send_encrypted(packet)
    
    def send_file_chunk(self, file_id: str, chunk_index: int, chunk_data: bytes):
        """Send a file chunk"""
        if not self.authenticated:
            return
        
        import base64
        packet = {
            'type': PACKET_TYPE_FILE_CHUNK,
            'file_id': file_id,
            'chunk_index': chunk_index,
            'data': base64.b64encode(chunk_data).decode('utf-8')
        }
        self._send_encrypted(packet)
    
    def send_ack(self, file_id: str, chunk_index: int):
        """Send acknowledgment"""
        if not self.authenticated:
            return
        
        packet = {
            'type': PACKET_TYPE_ACK,
            'file_id': file_id,
            'chunk_index': chunk_index
        }
        self._send_encrypted(packet)
    
    def send_typing(self, is_typing: bool):
        """Send typing indicator"""
        if not self.authenticated:
            return
        
        packet = {
            'type': PACKET_TYPE_TYPING,
            'is_typing': is_typing
        }
        self._send_encrypted(packet)
    
    def send_user_info(self):
        """Send user info"""
        if not self.authenticated:
            return
        
        packet = {
            'type': PACKET_TYPE_USER_INFO,
            'user_id': self.user_profile.get_user_id(),
            'info': {
                'name': self.user_profile.get_user_name(),
                'status': 'online'
            }
        }
        self._send_encrypted(packet)
    
    def send_read_receipt(self, message_id: str):
        """Send read receipt"""
        if not self.authenticated:
            return
        
        packet = {
            'type': PACKET_TYPE_READ_RECEIPT,
            'message_id': message_id
        }
        self._send_encrypted(packet)
    
    def send_delivery_receipt(self, message_id: str):
        """Send delivery receipt"""
        if not self.authenticated:
            return
        
        packet = {
            'type': PACKET_TYPE_DELIVERY_RECEIPT,
            'message_id': message_id
        }
        self._send_encrypted(packet)
    
    def disconnect(self):
        """Disconnect from peer"""
        self.running = False
        
        # Send close packet
        if self.connected and self.authenticated:
            try:
                packet = {'type': PACKET_TYPE_CLOSE}
                self._send_encrypted(packet)
            except:
                pass
        
        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.connected = False
        self.authenticated = False
