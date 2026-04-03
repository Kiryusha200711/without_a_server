"""
Base Transport for P2P Messenger
Abstract base class for all transports
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional, Any


class BaseTransport(ABC):
    """Abstract base class for network transports"""
    
    def __init__(self):
        self.connected = False
        self.authenticated = False
        self.peer_user_id: Optional[str] = None
        self.peer_name: Optional[str] = None
        
        # Callbacks
        self.on_text: Optional[Callable] = None
        self.on_file_info: Optional[Callable] = None
        self.on_file_chunk: Optional[Callable] = None
        self.on_ack: Optional[Callable] = None
        self.on_typing: Optional[Callable] = None
        self.on_user_info: Optional[Callable] = None
        self.on_read_receipt: Optional[Callable] = None
        self.on_delivery_receipt: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
    
    @abstractmethod
    async def connect(self, host: str, port: int) -> bool:
        """Connect to a peer"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from peer"""
        pass
    
    @abstractmethod
    async def send_text(self, message_id: str, text: str):
        """Send a text message"""
        pass
    
    @abstractmethod
    async def send_file_info(self, file_id: str, file_name: str, total_chunks: int, file_size: int):
        """Send file info before chunks"""
        pass
    
    @abstractmethod
    async def send_file_chunk(self, file_id: str, chunk_index: int, chunk_data: bytes):
        """Send a file chunk"""
        pass
    
    @abstractmethod
    async def send_ack(self, file_id: str, chunk_index: int):
        """Send acknowledgment for a file chunk"""
        pass
    
    @abstractmethod
    async def send_typing(self, is_typing: bool):
        """Send typing indicator"""
        pass
    
    @abstractmethod
    async def send_user_info(self):
        """Send user info"""
        pass
    
    @abstractmethod
    async def send_read_receipt(self, message_id: str):
        """Send read receipt for a message"""
        pass
    
    @abstractmethod
    async def send_delivery_receipt(self, message_id: str):
        """Send delivery receipt for a message"""
        pass
    
    def is_connected(self) -> bool:
        """Check if transport is connected"""
        return self.connected
    
    def is_authenticated(self) -> bool:
        """Check if transport is authenticated"""
        return self.authenticated
