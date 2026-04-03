"""
Database Helper for P2P Messenger
Singleton pattern for SQLite database access
"""

import sqlite3
import os
import json
import threading
from typing import List, Optional, Dict, Any
from datetime import datetime
from ..utils.constants import MSG_STATUS_SENDING


class DatabaseHelper:
    """Singleton database helper for P2P Messenger"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, data_dir: str):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, data_dir: str):
        if self._initialized:
            return
        
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, 'messenger.db')
        self._conn = None
        self._lock = threading.Lock()
        self._initialize_db()
        self._initialized = True
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-safe database connection"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _initialize_db(self):
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create contacts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                contact_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                host TEXT,
                port INTEGER,
                status INTEGER DEFAULT 0,
                last_seen REAL,
                avatar_path TEXT,
                transports_info TEXT,
                cert_fingerprint TEXT,
                address_book TEXT
            )
        ''')
        
        # Create messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                contact_id TEXT NOT NULL,
                type INTEGER DEFAULT 0,
                content TEXT,
                file_path TEXT,
                file_size INTEGER DEFAULT 0,
                timestamp REAL NOT NULL,
                is_outgoing INTEGER DEFAULT 0,
                status INTEGER DEFAULT 0,
                FOREIGN KEY (contact_id) REFERENCES contacts(contact_id) ON DELETE CASCADE
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_contact ON messages(contact_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
        
        conn.commit()
    
    def add_or_update_contact(self, contact) -> bool:
        """Add or update a contact"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO contacts 
                (contact_id, name, host, port, status, last_seen, avatar_path, 
                 transports_info, cert_fingerprint, address_book)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                contact.contact_id,
                contact.name,
                contact.address_book.get_best_address().ip if contact.address_book.get_best_address() else None,
                contact.address_book.get_best_address().port if contact.address_book.get_best_address() else None,
                contact.status,
                contact.last_seen,
                contact.avatar_path,
                json.dumps(contact.transports_info),
                contact.cert_fingerprint,
                json.dumps(contact.address_book.to_dict())
            ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding/updating contact: {e}")
            return False
    
    def get_contact(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get a contact by ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM contacts WHERE contact_id = ?', (contact_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"Error getting contact: {e}")
            return None
    
    def get_all_contacts(self) -> List[Dict[str, Any]]:
        """Get all contacts"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM contacts ORDER BY name')
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error getting contacts: {e}")
            return []
    
    def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact and all associated messages"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Delete messages first (cascade should handle this, but be explicit)
            cursor.execute('DELETE FROM messages WHERE contact_id = ?', (contact_id,))
            
            # Delete contact
            cursor.execute('DELETE FROM contacts WHERE contact_id = ?', (contact_id,))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting contact: {e}")
            return False
    
    def update_contact_status(self, contact_id: str, status: int) -> bool:
        """Update contact status"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            last_seen = datetime.utcnow().timestamp() if status != 0 else None
            
            cursor.execute('''
                UPDATE contacts SET status = ?, last_seen = ? WHERE contact_id = ?
            ''', (status, last_seen, contact_id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating contact status: {e}")
            return False
    
    def add_message(self, message) -> bool:
        """Add a message"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO messages 
                (id, contact_id, type, content, file_path, file_size, timestamp, is_outgoing, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                message.id,
                message.contact_id,
                message.type,
                message.content,
                message.file_path,
                message.file_size,
                message.timestamp / 1000.0,  # Convert to seconds
                1 if message.is_outgoing else 0,
                message.status
            ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding message: {e}")
            return False
    
    def get_messages_for_contact(self, contact_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages for a contact"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM messages 
                WHERE contact_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (contact_id, limit))
            
            rows = cursor.fetchall()
            messages = [dict(row) for row in rows]
            
            # Reverse to get chronological order
            messages.reverse()
            
            return messages
        except Exception as e:
            print(f"Error getting messages: {e}")
            return []
    
    def update_message_status(self, message_id: str, status: int) -> bool:
        """Update message status"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE messages SET status = ? WHERE id = ?
            ''', (status, message_id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating message status: {e}")
            return False
    
    def clean_orphaned_files(self, data_dir: str):
        """Clean up files not associated with any message or avatar"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get all file paths from messages
            cursor.execute('SELECT file_path FROM messages WHERE file_path IS NOT NULL')
            message_files = {row['file_path'] for row in cursor.fetchall()}
            
            # Get all avatar paths from contacts
            cursor.execute('SELECT avatar_path FROM contacts WHERE avatar_path IS NOT NULL')
            avatar_files = {row['avatar_path'] for row in cursor.fetchall()}
            
            valid_files = message_files | avatar_files
            
            # Check files in data directory
            files_dir = os.path.join(data_dir, 'files')
            if os.path.exists(files_dir):
                for filename in os.listdir(files_dir):
                    filepath = os.path.join(files_dir, filename)
                    if filepath not in valid_files and os.path.isfile(filepath):
                        try:
                            os.remove(filepath)
                            print(f"Cleaned orphaned file: {filepath}")
                        except Exception as e:
                            print(f"Error removing orphaned file: {e}")
        except Exception as e:
            print(f"Error cleaning orphaned files: {e}")
    
    def close(self):
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None
