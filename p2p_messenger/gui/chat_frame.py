"""
Chat Frame for P2P Messenger
Displays chat messages and allows sending new ones
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional


class ChatFrame(ttk.Frame):
    """Chat frame for messaging with a contact"""
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.current_contact_id = None
        self.chat_provider = None
        
        self.messages_frame = None
        self.message_entry = None
        self.typing_label = None
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create UI widgets"""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=20, pady=(15, 10))
        
        # Back button
        back_btn = ttk.Button(
            header_frame,
            text="← Back",
            command=lambda: self.controller.show_frame('home'),
            width=8
        )
        back_btn.pack(side=tk.LEFT)
        
        # Contact name
        self.contact_name_label = ttk.Label(
            header_frame,
            text="",
            style='Header.TLabel'
        )
        self.contact_name_label.pack(side=tk.LEFT, padx=(15, 0))
        
        # Status indicator
        self.status_label = ttk.Label(
            header_frame,
            text="",
            style='Subtitle.TLabel'
        )
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Messages area with scrollbar
        messages_container = ttk.Frame(self)
        messages_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Canvas for scrollable messages
        self.messages_canvas = tk.Canvas(messages_container, bg='#FFFFFF', highlightthickness=0)
        scrollbar = ttk.Scrollbar(messages_container, orient="vertical", command=self.messages_canvas.yview)
        
        self.messages_frame = ttk.Frame(self.messages_canvas)
        
        self.messages_frame.bind(
            "<Configure>",
            lambda e: self.messages_canvas.configure(scrollregion=self.messages_canvas.bbox("all"))
        )
        
        self.messages_canvas.create_window((0, 0), window=self.messages_frame, anchor="nw")
        self.messages_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mouse wheel
        self.messages_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        self.messages_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Typing indicator
        self.typing_label = ttk.Label(
            self,
            text="",
            style='Subtitle.TLabel',
            foreground='#666666'
        )
        self.typing_label.pack(anchor=tk.W, padx=20, pady=(0, 5))
        
        # Input area
        input_frame = ttk.Frame(self)
        input_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        # File attachment button
        attach_btn = ttk.Button(
            input_frame,
            text="📎",
            command=self._on_attach_file,
            width=3
        )
        attach_btn.pack(side=tk.LEFT)
        
        # Message entry
        self.message_entry = ttk.Entry(input_frame, font=('Helvetica', 11))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10))
        self.message_entry.bind('<Return>', self._on_send_message)
        self.message_entry.bind('<KeyRelease>', self._on_typing)
        
        # Send button
        send_btn = ttk.Button(
            input_frame,
            text="Send",
            command=self._on_send_message
        )
        send_btn.pack(side=tk.RIGHT)
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.messages_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def load_contact(self, contact_id: str):
        """Load chat with a contact"""
        self.current_contact_id = contact_id
        
        # Get contact info
        contact = self.controller.contact_provider.get_contact(contact_id)
        if contact:
            self.contact_name_label.config(text=contact.name)
            status_text = "Online" if contact.is_online() else "Offline"
            self.status_label.config(text=f"• {status_text}")
        
        # Clear previous messages
        for widget in self.messages_frame.winfo_children():
            widget.destroy()
        
        # Get chat provider
        self.chat_provider = self.controller.get_chat_provider(contact_id)
        self.chat_provider.on_message_received = self._on_message_received
        self.chat_provider.on_typing_status = self._on_typing_status
        
        # Connect to contact
        self.chat_provider.connect()
        
        # Load message history
        self._load_messages()
    
    def _load_messages(self):
        """Load message history"""
        if not self.chat_provider:
            return
        
        for message in self.chat_provider.messages:
            self._add_message_to_ui(message)
        
        # Scroll to bottom
        self.messages_canvas.update_idletasks()
        self.messages_canvas.yview_moveto(1.0)
    
    def _add_message_to_ui(self, message):
        """Add a message bubble to the UI"""
        # Date separator if needed
        current_date = message.get_formatted_date()
        last_widget = self.messages_frame.winfo_children()[-1] if self.messages_frame.winfo_children() else None
        
        if last_widget is None or getattr(last_widget, 'date', None) != current_date:
            date_label = ttk.Label(
                self.messages_frame,
                text=current_date,
                style='Subtitle.TLabel',
                font=('Helvetica', 9)
            )
            date_label.date = current_date
            date_label.pack(pady=10)
        
        # Create message bubble
        bubble_frame = ttk.Frame(self.messages_frame)
        bubble_frame.pack(fill=tk.X, pady=2, padx=10)
        
        if message.is_outgoing:
            # Outgoing message (right aligned)
            content_frame = ttk.Frame(bubble_frame, style='Outgoing.TFrame')
            content_frame.pack(side=tk.RIGHT, anchor=tk.E)
            
            msg_label = tk.Label(
                content_frame,
                text=message.content,
                bg='#DCF8C6',
                fg='#000000',
                wraplength=400,
                justify=tk.LEFT,
                padx=10,
                pady=8,
                font=('Helvetica', 10)
            )
            msg_label.pack(anchor=tk.E)
            
            # Status indicator
            status_text = {'sending': '⏳', 'sent': '✓', 'delivered': '✓✓', 'read': '✓✓', 'error': '❌'}
            status_label = tk.Label(
                content_frame,
                text=status_text.get(message.get_status_name(), ''),
                bg='#DCF8C6',
                fg='#666666',
                font=('Helvetica', 8)
            )
            status_label.pack(anchor=tk.E, padx=(5, 5), pady=(0, 3))
            
        else:
            # Incoming message (left aligned)
            content_frame = ttk.Frame(bubble_frame, style='Incoming.TFrame')
            content_frame.pack(side=tk.LEFT, anchor=tk.W)
            
            msg_label = tk.Label(
                content_frame,
                text=message.content,
                bg='#FFFFFF',
                fg='#000000',
                wraplength=400,
                justify=tk.LEFT,
                padx=10,
                pady=8,
                font=('Helvetica', 10),
                relief='solid',
                borderwidth=1
            )
            msg_label.pack(anchor=tk.W)
        
        # Time label
        time_label = ttk.Label(
            bubble_frame,
            text=message.get_formatted_time(),
            style='Subtitle.TLabel',
            font=('Helvetica', 8)
        )
        
        if message.is_outgoing:
            time_label.pack(side=tk.RIGHT, anchor=tk.SE, padx=(5, 0))
        else:
            time_label.pack(side=tk.LEFT, anchor=tk.SW, padx=(5, 0))
        
        # Scroll to bottom
        self.messages_canvas.update_idletasks()
        self.messages_canvas.yview_moveto(1.0)
    
    def _on_message_received(self, message):
        """Handle received message"""
        # Schedule UI update on main thread
        self.after(0, lambda: self._add_message_to_ui(message))
    
    def _on_typing_status(self, is_typing: bool):
        """Handle typing status from peer"""
        if is_typing:
            self.typing_label.config(text="typing...")
        else:
            self.typing_label.config(text="")
    
    def _on_send_message(self, event=None):
        """Handle send message"""
        if not self.chat_provider:
            return
        
        text = self.message_entry.get().strip()
        if not text:
            return
        
        # Send message
        self.chat_provider.send_text_message(text)
        
        # Clear entry
        self.message_entry.delete(0, tk.END)
        
        # Cancel typing indicator
        self.chat_provider.send_typing(False)
    
    def _on_typing(self, event=None):
        """Handle typing in message entry"""
        if not self.chat_provider:
            return
        
        # Send typing indicator
        self.chat_provider.send_typing(True)
    
    def _on_attach_file(self):
        """Handle file attachment"""
        file_path = filedialog.askopenfilename(
            title="Select File",
            filetypes=[
                ("All Files", "*.*"),
                ("Text Files", "*.txt"),
                ("Images", "*.jpg *.jpeg *.png *.gif"),
                ("Documents", "*.pdf *.doc *.docx"),
                ("Audio", "*.mp3 *.wav *.ogg")
            ]
        )
        
        if file_path and self.chat_provider:
            if self.chat_provider.send_file(file_path):
                messagebox.showinfo("File Transfer", "File transfer started")
            else:
                messagebox.showerror("Error", "Failed to send file. Make sure you're connected.")
