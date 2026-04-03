"""
P2P Messenger Application
Main GUI application class
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
from typing import Dict, Optional

from ..models.user_profile import UserProfile
from ..models.contact import Contact
from ..core.database_helper import DatabaseHelper
from ..security.cert_store import CertificateStore
from ..providers.contact_provider import ContactProvider
from ..utils.constants import (
    APP_NAME, APP_VERSION, DATA_DIR_NAME,
    WINDOW_WIDTH, WINDOW_HEIGHT, COLOR_PRIMARY, COLOR_BACKGROUND
)


class P2PMessengerApp:
    """Main P2P Messenger Application"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(800, 600)
        
        # Setup styles
        self._setup_styles()
        
        # Data directory
        self.data_dir = os.path.join(os.path.expanduser('~'), DATA_DIR_NAME)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, 'files'), exist_ok=True)
        
        # Core components
        self.db_helper: Optional[DatabaseHelper] = None
        self.user_profile: Optional[UserProfile] = None
        self.cert_store: Optional[CertificateStore] = None
        self.contact_provider: Optional[ContactProvider] = None
        
        # Chat providers (one per active chat)
        self.chat_providers: Dict[str, any] = {}
        
        # Current chat contact
        self.current_chat_contact_id: Optional[str] = None
        
        # Frames
        self.main_container = None
        self.register_frame = None
        self.home_frame = None
        self.chat_frame = None
        self.profile_frame = None
        
        # Initialize in background
        self.init_status_var = tk.StringVar(value="Initializing...")
        self._show_splash()
        self._init_background()
    
    def _setup_styles(self):
        """Setup ttk styles"""
        style = ttk.Style()
        
        # Configure colors
        style.configure('TFrame', background=COLOR_BACKGROUND)
        style.configure('TLabel', background=COLOR_BACKGROUND, foreground='#000000')
        style.configure('Header.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Subtitle.TLabel', font=('Helvetica', 10), foreground='#666666')
        
        style.configure('TButton', font=('Helvetica', 10))
        style.map('TButton',
            background=[('active', COLOR_PRIMARY)])
        
        style.configure('TEntry', fieldbackground='#FFFFFF', font=('Helvetica', 10))
        
        # Custom styles for messages
        style.configure('Outgoing.TFrame', background='#DCF8C6')
        style.configure('Incoming.TFrame', background='#FFFFFF')
    
    def _show_splash(self):
        """Show splash screen"""
        self.splash = tk.Toplevel(self.root)
        self.splash.title(APP_NAME)
        self.splash.geometry("400x300")
        self.splash.resizable(False, False)
        self.splash.configure(bg=COLOR_PRIMARY)
        
        # Center the splash
        self.splash.update_idletasks()
        x = (self.splash.winfo_screenwidth() - 400) // 2
        y = (self.splash.winfo_screenheight() - 300) // 2
        self.splash.geometry(f"400x300+{x}+{y}")
        
        # Remove window decorations
        self.splash.overrideredirect(True)
        
        # Logo/Title
        title_label = tk.Label(
            self.splash,
            text=APP_NAME,
            font=('Helvetica', 24, 'bold'),
            bg=COLOR_PRIMARY,
            fg='white'
        )
        title_label.pack(pady=(80, 10))
        
        version_label = tk.Label(
            self.splash,
            text=f"Version {APP_VERSION}",
            font=('Helvetica', 10),
            bg=COLOR_PRIMARY,
            fg='white'
        )
        version_label.pack()
        
        # Status label
        status_label = tk.Label(
            self.splash,
            textvariable=self.init_status_var,
            font=('Helvetica', 10),
            bg=COLOR_PRIMARY,
            fg='white'
        )
        status_label.pack(pady=(40, 0))
        
        # Progress bar
        self.progress = ttk.Progressbar(
            self.splash,
            mode='indeterminate',
            length=300
        )
        self.progress.pack(pady=(20, 0))
        self.progress.start(10)
        
        # Hide main window temporarily
        self.root.withdraw()
    
    def _init_background(self):
        """Initialize app in background thread"""
        def init():
            try:
                self.init_status_var.set("Loading database...")
                self.db_helper = DatabaseHelper(self.data_dir)
                
                self.init_status_var.set("Loading profile...")
                self.user_profile = UserProfile(self.data_dir)
                
                self.init_status_var.set("Loading certificates...")
                self.cert_store = CertificateStore(self.data_dir)
                
                # Schedule UI update on main thread
                self.root.after(0, self._on_init_complete)
                
            except Exception as e:
                print(f"Initialization error: {e}")
                self.root.after(0, lambda: self._on_init_error(str(e)))
        
        thread = threading.Thread(target=init, daemon=True)
        thread.start()
    
    def _on_init_complete(self):
        """Called when initialization is complete"""
        self.splash.destroy()
        self.root.deiconify()
        
        # Check if user has a profile
        if not self.user_profile.has_profile():
            self._show_register_frame()
        else:
            self._start_services()
            self._show_main_ui()
    
    def _on_init_error(self, error_msg: str):
        """Called when initialization fails"""
        self.splash.destroy()
        messagebox.showerror("Initialization Error", f"Failed to initialize:\n{error_msg}")
        self.root.destroy()
    
    def _show_register_frame(self):
        """Show registration frame"""
        from .register_frame import RegisterFrame
        
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        self.register_frame = RegisterFrame(
            self.main_container,
            self.user_profile,
            self.on_registration_complete
        )
        self.register_frame.pack(fill=tk.BOTH, expand=True)
    
    def on_registration_complete(self):
        """Called when registration is complete"""
        self.register_frame.destroy()
        self._start_services()
        self._show_main_ui()
    
    def _start_services(self):
        """Start background services"""
        self.init_status_var.set("Starting services...")
        
        self.contact_provider = ContactProvider(
            self.user_profile,
            self.cert_store,
            self.db_helper,
            self.data_dir
        )
        
        # Setup callbacks
        self.contact_provider.on_contact_added = self._on_contact_added
        self.contact_provider.on_contact_removed = self._on_contact_removed
        self.contact_provider.on_contact_updated = self._on_contact_updated
        
        # Start services
        self.contact_provider.start()
    
    def _show_main_ui(self):
        """Show main UI with frames"""
        # Clear existing content
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Create main container
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create frames
        from .home_frame import HomeFrame
        from .chat_frame import ChatFrame
        from .profile_frame import ProfileFrame
        
        self.home_frame = HomeFrame(self.main_container, self)
        self.chat_frame = ChatFrame(self.main_container, self)
        self.profile_frame = ProfileFrame(self.main_container, self)
        
        # Show home frame initially
        self.show_frame('home')
        
        # Setup window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def show_frame(self, frame_name: str):
        """Show a specific frame"""
        # Hide all frames
        if self.home_frame:
            self.home_frame.pack_forget()
        if self.chat_frame:
            self.chat_frame.pack_forget()
        if self.profile_frame:
            self.profile_frame.pack_forget()
        
        # Show requested frame
        if frame_name == 'home':
            self.home_frame.pack(fill=tk.BOTH, expand=True)
            self.current_chat_contact_id = None
        elif frame_name == 'chat':
            self.chat_frame.pack(fill=tk.BOTH, expand=True)
        elif frame_name == 'profile':
            self.profile_frame.pack(fill=tk.BOTH, expand=True)
    
    def open_chat(self, contact_id: str):
        """Open chat with a contact"""
        self.current_chat_contact_id = contact_id
        self.chat_frame.load_contact(contact_id)
        self.show_frame('chat')
    
    def get_chat_provider(self, contact_id: str):
        """Get or create chat provider for a contact"""
        if contact_id not in self.chat_providers:
            self.chat_providers[contact_id] = self.contact_provider.create_chat_provider(contact_id)
        return self.chat_providers[contact_id]
    
    def _on_contact_added(self, contact: Contact):
        """Callback when a contact is added"""
        if self.home_frame:
            self.home_frame.add_contact(contact)
    
    def _on_contact_removed(self, contact_id: str):
        """Callback when a contact is removed"""
        if self.home_frame:
            self.home_frame.remove_contact(contact_id)
    
    def _on_contact_updated(self, contact: Contact):
        """Callback when a contact is updated"""
        if self.home_frame:
            self.home_frame.update_contact(contact)
    
    def on_close(self):
        """Handle window close"""
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            # Stop services
            if self.contact_provider:
                self.contact_provider.stop()
            
            # Close database
            if self.db_helper:
                self.db_helper.close()
            
            # Destroy window
            self.root.destroy()
    
    def run(self):
        """Run the application"""
        self.root.mainloop()
