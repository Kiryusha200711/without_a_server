"""
Registration Frame for P2P Messenger
Allows users to create a new account
"""

import tkinter as tk
from tkinter import ttk, messagebox
import re
from ..utils.constants import COLOR_PRIMARY, COLOR_BACKGROUND


class RegisterFrame(ttk.Frame):
    """Registration frame for new users"""
    
    def __init__(self, parent, user_profile, on_complete_callback):
        super().__init__(parent)
        self.user_profile = user_profile
        self.on_complete = on_complete_callback
        
        self.configure(style='TFrame')
        self._create_widgets()
    
    def _create_widgets(self):
        """Create registration widgets"""
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Welcome to P2P Messenger",
            style='Header.TLabel'
        )
        title_label.pack(pady=(40, 10))
        
        subtitle_label = ttk.Label(
            main_frame,
            text="Create your account to get started",
            style='Subtitle.TLabel'
        )
        subtitle_label.pack(pady=(0, 40))
        
        # Form frame
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X, pady=20)
        
        # Username label and entry
        username_label = ttk.Label(form_frame, text="Username:")
        username_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.username_entry = ttk.Entry(form_frame, font=('Helvetica', 12))
        self.username_entry.pack(fill=tk.X, pady=(0, 20))
        self.username_entry.bind('<Return>', lambda e: self._on_register())
        
        # User ID preview (will be generated)
        id_frame = ttk.Frame(form_frame)
        id_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(id_frame, text="Your User ID (auto-generated):").pack(anchor=tk.W)
        self.id_label = ttk.Label(
            id_frame,
            text="Will be generated upon registration",
            font=('Courier', 9),
            foreground='#666666'
        )
        self.id_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Info text
        info_text = ttk.Label(
            form_frame,
            text="Your unique ID will be used to identify you on the network. "
                 "Keep it safe as it cannot be changed later.",
            wraplength=400,
            justify=tk.LEFT,
            style='Subtitle.TLabel'
        )
        info_text.pack(pady=(0, 30))
        
        # Register button
        self.register_btn = ttk.Button(
            form_frame,
            text="Create Account",
            command=self._on_register,
            style='TButton'
        )
        self.register_btn.pack(fill=tk.X, pady=10)
        
        # Features list
        features_frame = ttk.Frame(main_frame)
        features_frame.pack(fill=tk.BOTH, expand=True, pady=(40, 0))
        
        features_title = ttk.Label(
            features_frame,
            text="Features:",
            font=('Helvetica', 11, 'bold')
        )
        features_title.pack(anchor=tk.W, pady=(0, 10))
        
        features = [
            "✓ End-to-end encrypted messaging",
            "✓ No central servers - fully decentralized",
            "✓ Send text messages, files, and audio",
            "✓ Works on local network and internet",
            "✓ Your data stays on your device"
        ]
        
        for feature in features:
            ttk.Label(
                features_frame,
                text=feature,
                style='Subtitle.TLabel'
            ).pack(anchor=tk.W, pady=2)
    
    def _on_register(self):
        """Handle registration"""
        username = self.username_entry.get().strip()
        
        # Validate username
        if not username:
            messagebox.showerror("Error", "Please enter a username")
            return
        
        if len(username) < 3:
            messagebox.showerror("Error", "Username must be at least 3 characters long")
            return
        
        if len(username) > 30:
            messagebox.showerror("Error", "Username must be less than 30 characters")
            return
        
        # Disable button during registration
        self.register_btn.config(state='disabled')
        self.register_btn.config(text="Creating Account...")
        
        # Create account in background
        import threading
        def create_account():
            success = self.user_profile.create_account(username)
            
            # Update UI on main thread
            self.after(0, lambda: self._on_registration_result(success, username))
        
        thread = threading.Thread(target=create_account, daemon=True)
        thread.start()
    
    def _on_registration_result(self, success: bool, username: str):
        """Handle registration result"""
        self.register_btn.config(state='normal')
        self.register_btn.config(text="Create Account")
        
        if success:
            # Update ID label
            user_id = self.user_profile.get_user_id()
            self.id_label.config(text=f"ID: {user_id[:8]}...", foreground='#4CAF50')
            
            messagebox.showinfo(
                "Success",
                f"Account created successfully!\n\n"
                f"Username: {username}\n"
                f"User ID: {user_id}\n\n"
                f"You can now start using P2P Messenger."
            )
            
            # Call completion callback
            self.on_complete()
        else:
            messagebox.showerror("Error", "Failed to create account. Please try again.")
