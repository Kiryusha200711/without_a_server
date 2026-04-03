"""
Chat Provider for P2P Messenger
Handles chat logic for a single contact
"""

import threading
import os
import time
from typing import List, Optional, Callable, Dict
from datetime import datetime

from ..models.message import Message
from ..utils.constants import (
    MSG_TYPE_TEXT, MSG_TYPE_FILE, MSG_STATUS_SENT,
    MSG_STATUS_DELIVERED, CHUNK_SIZE, FILE_CHUNK_TIMEOUT, MESSAGE_RETRY_COUNT
)


class ChatProvider:
    """Manages chat with a single contact"""
    
    def __init__(self, contact_id: str, contact_provider):
        self.contact_id = contact_id
        self.contact_provider = contact_provider
        
        # Messages cache
        self.messages: List[Message] = []
        
        # File transfer state
        self.incoming_files: Dict[str, dict] = {}  # file_id -> {chunks, total, filename, size}
        self.pending_acks: Dict[str, dict] = {}  # file_id -> {chunk_idx: event}
        
        # Typing state
        self.is_typing = False
        self.typing_timer: Optional[threading.Timer] = None
        
        # Callbacks
        self.on_message_received: Optional[Callable] = None
        self.on_typing_status: Optional[Callable] = None
        self.on_file_progress: Optional[Callable] = None
        
        # Load message history
        self._load_messages()
    
    def _load_messages(self):
        """Load message history from database"""
        messages_data = self.contact_provider.db_helper.get_messages_for_contact(self.contact_id, 100)
        for msg_data in messages_data:
            msg = Message.from_dict(msg_data)
            self.messages.append(msg)
    
    def connect(self) -> bool:
        """Connect to the contact"""
        return self.contact_provider.connect_to_contact(self.contact_id)
    
    def get_transport(self):
        """Get the transport for this contact"""
        return self.contact_provider.get_transport(self.contact_id)
    
    def send_text_message(self, text: str) -> Optional[Message]:
        """Send a text message"""
        transport = self.get_transport()
        if not transport or not transport.is_authenticated():
            # Queue message for later (not implemented)
            return None
        
        # Create message
        message = Message(
            contact_id=self.contact_id,
            msg_type=MSG_TYPE_TEXT,
            content=text,
            is_outgoing=True
        )
        
        # Save to database
        self.contact_provider.db_helper.add_message(message)
        self.messages.append(message)
        
        # Send via transport
        transport.send_text(message.id, text)
        
        # Update status to sent
        message.status = MSG_STATUS_SENT
        self.contact_provider.db_helper.update_message_status(message.id, MSG_STATUS_SENT)
        
        return message
    
    def send_file(self, file_path: str) -> bool:
        """Send a file"""
        transport = self.get_transport()
        if not transport or not transport.is_authenticated():
            return False
        
        try:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            file_id = f"{int(time.time() * 1000)}_{file_name}"
            
            # Calculate chunks
            total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
            
            # Send file info
            transport.send_file_info(file_id, file_name, total_chunks, file_size)
            
            # Send chunks in background
            threading.Thread(
                target=self._send_file_chunks,
                args=(transport, file_id, file_path, total_chunks),
                daemon=True
            ).start()
            
            return True
        except Exception as e:
            print(f"Error sending file: {e}")
            return False
    
    def _send_file_chunks(self, transport, file_id: str, file_path: str, total_chunks: int):
        """Send file chunks with ACK waiting"""
        try:
            with open(file_path, 'rb') as f:
                for idx in range(total_chunks):
                    chunk = f.read(CHUNK_SIZE)
                    
                    # Send chunk with retry
                    success = False
                    for retry in range(MESSAGE_RETRY_COUNT):
                        transport.send_file_chunk(file_id, idx, chunk)
                        
                        # Wait for ACK
                        if self._wait_for_ack(file_id, idx):
                            success = True
                            break
                    
                    if not success:
                        print(f"Failed to send chunk {idx} after {MESSAGE_RETRY_COUNT} retries")
                        break
            
            # Create message record after successful transfer
            file_size = os.path.getsize(file_path)
            message = Message(
                contact_id=self.contact_id,
                msg_type=MSG_TYPE_FILE,
                content=os.path.basename(file_path),
                file_path=file_path,
                file_size=file_size,
                is_outgoing=True,
                status=MSG_STATUS_DELIVERED
            )
            self.contact_provider.db_helper.add_message(message)
            self.messages.append(message)
            
            if self.on_message_received:
                self.on_message_received(message)
                
        except Exception as e:
            print(f"Error sending file chunks: {e}")
    
    def _wait_for_ack(self, file_id: str, chunk_idx: int, timeout: float = FILE_CHUNK_TIMEOUT) -> bool:
        """Wait for ACK for a chunk"""
        event = threading.Event()
        
        if file_id not in self.pending_acks:
            self.pending_acks[file_id] = {}
        self.pending_acks[file_id][chunk_idx] = event
        
        # Wait for ACK
        result = event.wait(timeout)
        
        # Cleanup
        if file_id in self.pending_acks and chunk_idx in self.pending_acks[file_id]:
            del self.pending_acks[file_id][chunk_idx]
        
        return result
    
    def on_text_received(self, message_id: str, text: str):
        """Handle received text message"""
        message = Message(
            contact_id=self.contact_id,
            msg_type=MSG_TYPE_TEXT,
            content=text,
            is_outgoing=False,
            status=MSG_STATUS_DELIVERED
        )
        message.id = message_id
        
        # Save to database
        self.contact_provider.db_helper.add_message(message)
        self.messages.append(message)
        
        # Notify GUI
        if self.on_message_received:
            self.on_message_received(message)
        
        # Send delivery receipt (optional)
        transport = self.get_transport()
        if transport:
            transport.send_delivery_receipt(message_id)
    
    def on_file_info_received(self, file_id: str, file_name: str, total_chunks: int, file_size: int):
        """Handle received file info"""
        self.incoming_files[file_id] = {
            'chunks': {},
            'total': total_chunks,
            'filename': file_name,
            'size': file_size,
            'received': 0
        }
    
    def on_file_chunk_received(self, file_id: str, chunk_idx: int, chunk_data: bytes):
        """Handle received file chunk"""
        if file_id not in self.incoming_files:
            return
        
        file_info = self.incoming_files[file_id]
        file_info['chunks'][chunk_idx] = chunk_data
        file_info['received'] += 1
        
        # Send ACK
        transport = self.get_transport()
        if transport:
            transport.send_ack(file_id, chunk_idx)
        
        # Check if all chunks received
        if file_info['received'] >= file_info['total']:
            self._assemble_file(file_id)
    
    def on_ack_received(self, file_id: str, chunk_idx: int):
        """Handle received ACK"""
        if file_id in self.pending_acks and chunk_idx in self.pending_acks[file_id]:
            self.pending_acks[file_id][chunk_idx].set()
    
    def _assemble_file(self, file_id: str):
        """Assemble received file from chunks"""
        try:
            file_info = self.incoming_files[file_id]
            
            # Determine save path
            files_dir = os.path.join(self.contact_provider.data_dir, 'files')
            os.makedirs(files_dir, exist_ok=True)
            
            save_path = os.path.join(files_dir, file_info['filename'])
            
            # Handle duplicate filenames
            base, ext = os.path.splitext(file_info['filename'])
            counter = 1
            while os.path.exists(save_path):
                save_path = os.path.join(files_dir, f"{base}_{counter}{ext}")
                counter += 1
            
            # Write file
            with open(save_path, 'wb') as f:
                for idx in range(file_info['total']):
                    f.write(file_info['chunks'][idx])
            
            # Create message
            message = Message(
                contact_id=self.contact_id,
                msg_type=MSG_TYPE_FILE,
                content=file_info['filename'],
                file_path=save_path,
                file_size=file_info['size'],
                is_outgoing=False,
                status=MSG_STATUS_DELIVERED
            )
            
            self.contact_provider.db_helper.add_message(message)
            self.messages.append(message)
            
            # Notify GUI
            if self.on_message_received:
                self.on_message_received(message)
            
            # Cleanup
            del self.incoming_files[file_id]
            
        except Exception as e:
            print(f"Error assembling file: {e}")
    
    def send_typing(self, is_typing: bool):
        """Send typing indicator"""
        transport = self.get_transport()
        if transport:
            transport.send_typing(is_typing)
    
    def on_typing_received(self, is_typing: bool):
        """Handle received typing indicator"""
        if self.on_typing_status:
            self.on_typing_status(is_typing)
    
    def mark_as_read(self, message_id: str):
        """Mark a message as read"""
        self.contact_provider.db_helper.update_message_status(message_id, 3)  # READ
        
        # Send read receipt
        transport = self.get_transport()
        if transport:
            transport.send_read_receipt(message_id)
