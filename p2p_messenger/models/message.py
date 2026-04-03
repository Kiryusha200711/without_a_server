"""
Message Model for P2P Messenger
"""

import uuid
from typing import Optional
from datetime import datetime
from ..utils.constants import (
    MSG_TYPE_TEXT, MSG_STATUS_SENDING,
    MSG_TYPE_FILE, MSG_TYPE_IMAGE, MSG_TYPE_AUDIO
)


class Message:
    """Represents a chat message"""
    
    def __init__(self, contact_id: str, msg_type: int = MSG_TYPE_TEXT, 
                 content: str = "", file_path: Optional[str] = None,
                 file_size: int = 0, is_outgoing: bool = False):
        self.id = str(uuid.uuid4())
        self.contact_id = contact_id
        self.type = msg_type
        self.content = content
        self.file_path = file_path
        self.file_size = file_size
        self.timestamp = datetime.utcnow().timestamp() * 1000  # milliseconds
        self.is_outgoing = is_outgoing
        self.status = MSG_STATUS_SENDING
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'type': self.type,
            'content': self.content,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'timestamp': self.timestamp,
            'is_outgoing': self.is_outgoing,
            'status': self.status
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        msg = cls(
            data['contact_id'],
            data.get('type', MSG_TYPE_TEXT),
            data.get('content', ''),
            data.get('file_path'),
            data.get('file_size', 0),
            data.get('is_outgoing', False)
        )
        msg.id = data['id']
        msg.timestamp = data.get('timestamp', datetime.utcnow().timestamp() * 1000)
        msg.status = data.get('status', MSG_STATUS_SENDING)
        return msg
    
    def get_type_name(self) -> str:
        """Get human-readable type name"""
        types = {
            MSG_TYPE_TEXT: 'text',
            MSG_TYPE_FILE: 'file',
            MSG_TYPE_IMAGE: 'image',
            MSG_TYPE_AUDIO: 'audio'
        }
        return types.get(self.type, 'unknown')
    
    def get_status_name(self) -> str:
        """Get human-readable status name"""
        from ..utils.constants import (
            MSG_STATUS_SENDING, MSG_STATUS_SENT, MSG_STATUS_DELIVERED,
            MSG_STATUS_READ, MSG_STATUS_ERROR
        )
        statuses = {
            MSG_STATUS_SENDING: 'sending',
            MSG_STATUS_SENT: 'sent',
            MSG_STATUS_DELIVERED: 'delivered',
            MSG_STATUS_READ: 'read',
            MSG_STATUS_ERROR: 'error'
        }
        return statuses.get(self.status, 'unknown')
    
    def get_formatted_time(self) -> str:
        """Get formatted timestamp"""
        dt = datetime.fromtimestamp(self.timestamp / 1000)
        return dt.strftime('%H:%M')
    
    def get_formatted_date(self) -> str:
        """Get formatted date"""
        dt = datetime.fromtimestamp(self.timestamp / 1000)
        return dt.strftime('%Y-%m-%d')
