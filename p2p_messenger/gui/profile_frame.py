"""
Profile Frame for P2P Messenger
Displays user profile and settings
"""

import tkinter as tk
from tkinter import ttk, messagebox


class ProfileFrame(ttk.Frame):
    """Profile frame showing user info and settings"""
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self._create_widgets()
        self._load_profile()
    
    def _create_widgets(self):
        """Create UI widgets"""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        # Back button
        back_btn = ttk.Button(
            header_frame,
            text="← Back",
            command=lambda: self.controller.show_frame('home'),
            width=8
        )
        back_btn.pack(side=tk.LEFT)
        
        title_label = ttk.Label(
            header_frame,
            text="Profile",
            style='Header.TLabel'
        )
        title_label.pack(side=tk.LEFT, padx=(15, 0))
        
        # Main content
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # User ID section
        id_frame = ttk.LabelFrame(content_frame, text="Your Identity", padding=15)
        id_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(id_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.username_label = ttk.Label(id_frame, text="")
        self.username_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Label(id_frame, text="User ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.user_id_label = ttk.Label(id_frame, text="", font=('Courier', 9))
        self.user_id_label.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Label(id_frame, text="Fingerprint:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.fingerprint_label = ttk.Label(id_frame, text="", font=('Courier', 8), wraplength=400)
        self.fingerprint_label.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Copy fingerprint button
        copy_btn = ttk.Button(
            id_frame,
            text="Copy Fingerprint",
            command=self._copy_fingerprint
        )
        copy_btn.grid(row=3, column=1, sticky=tk.W, pady=(10, 0))
        
        # Network info section
        network_frame = ttk.LabelFrame(content_frame, text="Network Information", padding=15)
        network_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(network_frame, text="Listening Port:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.port_label = ttk.Label(network_frame, text="37021")
        self.port_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Label(network_frame, text="Broadcast Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.broadcast_label = ttk.Label(network_frame, text="37020")
        self.broadcast_label.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Info text
        info_text = ttk.Label(
            network_frame,
            text="Share your IP address and port (37021) with contacts to connect.\n"
                 "For internet connections, you may need to set up port forwarding\n"
                 "on your router.",
            wraplength=450,
            justify=tk.LEFT,
            style='Subtitle.TLabel'
        )
        info_text.grid(row=2, column=0, columnspan=2, pady=(15, 0))
        
        # Security section
        security_frame = ttk.LabelFrame(content_frame, text="Security", padding=15)
        security_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(
            security_frame,
            text="All messages are end-to-end encrypted using:\n"
                 "• ECDH key exchange (SECP256R1)\n"
                 "• AES-256-GCM encryption\n"
                 "• HMAC-SHA256 authentication\n"
                 "• RSA-3072 signatures",
            wraplength=450,
            justify=tk.LEFT,
            style='Subtitle.TLabel'
        ).pack(anchor=tk.W)
        
        # Data section
        data_frame = ttk.LabelFrame(content_frame, text="Data & Storage", padding=15)
        data_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(data_frame, text="Data Directory:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.data_dir_label = ttk.Label(data_frame, text=self.controller.data_dir, wraplength=400)
        self.data_dir_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        open_btn = ttk.Button(
            data_frame,
            text="Open Folder",
            command=self._open_data_folder
        )
        open_btn.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        
        # About section
        about_frame = ttk.LabelFrame(content_frame, text="About", padding=15)
        about_frame.pack(fill=tk.BOTH, expand=True)
        
        from ..utils.constants import APP_NAME, APP_VERSION
        
        ttk.Label(
            about_frame,
            text=f"{APP_NAME} v{APP_VERSION}\n\n"
                 "A fully decentralized peer-to-peer messaging application.\n"
                 "No servers, no tracking, complete privacy.\n\n"
                 "Features:\n"
                 "• End-to-end encrypted messaging\n"
                 "• File transfer with chunking and ACK\n"
                 "• Typing indicators\n"
                 "• Read receipts\n"
                 "• Local network discovery via UDP broadcast\n"
                 "• Manual contact addition by IP/hostname\n"
                 "• Certificate-based identity verification",
            wraplength=450,
            justify=tk.LEFT,
            style='Subtitle.TLabel'
        ).pack(anchor=tk.W)
    
    def _load_profile(self):
        """Load profile information"""
        if self.controller.user_profile:
            self.username_label.config(text=self.controller.user_profile.get_user_name())
            self.user_id_label.config(text=self.controller.user_profile.get_user_id())
            
            fingerprint = self.controller.user_profile.get_certificate_fingerprint()
            if fingerprint:
                # Format fingerprint for display
                formatted = ':'.join(fingerprint[i:i+2] for i in range(0, len(fingerprint), 2))
                self.fingerprint_label.config(text=formatted[:64] + "..." if len(formatted) > 64 else formatted)
    
    def _copy_fingerprint(self):
        """Copy fingerprint to clipboard"""
        fingerprint = self.controller.user_profile.get_certificate_fingerprint()
        if fingerprint:
            self.clipboard_clear()
            self.clipboard_append(fingerprint)
            messagebox.showinfo("Copied", "Fingerprint copied to clipboard!")
    
    def _open_data_folder(self):
        """Open data folder in file explorer"""
        import os
        import subprocess
        import platform
        
        data_dir = self.controller.data_dir
        if os.path.exists(data_dir):
            try:
                if platform.system() == 'Windows':
                    os.startfile(data_dir)
                elif platform.system() == 'Darwin':
                    subprocess.run(['open', data_dir])
                else:
                    subprocess.run(['xdg-open', data_dir])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open folder: {e}")
        else:
            messagebox.showinfo("Info", f"Data directory does not exist yet:\n{data_dir}")
