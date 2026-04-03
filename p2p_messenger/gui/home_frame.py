"""
Home Frame for P2P Messenger
Displays contacts list and allows adding new contacts
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional


class HomeFrame(ttk.Frame):
    """Home frame showing contacts list"""
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.contacts_listbox = None
        
        self._create_widgets()
        self._load_contacts()
    
    def _create_widgets(self):
        """Create UI widgets"""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        title_label = ttk.Label(
            header_frame,
            text="Contacts",
            style='Header.TLabel'
        )
        title_label.pack(side=tk.LEFT)
        
        # Add button
        add_btn = ttk.Button(
            header_frame,
            text="+ Add Contact",
            command=self._on_add_contact
        )
        add_btn.pack(side=tk.RIGHT)
        
        # Profile button
        profile_btn = ttk.Button(
            header_frame,
            text="👤 Profile",
            command=lambda: self.controller.show_frame('profile')
        )
        profile_btn.pack(side=tk.RIGHT, padx=(0, 10))
        
        # Contacts listbox with scrollbar
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.contacts_listbox = tk.Listbox(
            list_frame,
            font=('Helvetica', 11),
            yscrollcommand=scrollbar.set,
            height=20
        )
        self.contacts_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.contacts_listbox.yview)
        
        # Bind double-click to open chat
        self.contacts_listbox.bind('<Double-Button-1>', self._on_contact_double_click)
        
        # Status bar
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        self.status_label = ttk.Label(
            status_frame,
            text="Ready",
            style='Subtitle.TLabel'
        )
        self.status_label.pack(side=tk.LEFT)
    
    def _load_contacts(self):
        """Load contacts from provider"""
        self.contacts_listbox.delete(0, tk.END)
        
        contacts = self.controller.contact_provider.get_all_contacts()
        for contact in contacts:
            status_icon = "🟢" if contact.is_online() else "⚫"
            display_text = f"{status_icon} {contact.name}"
            
            self.contacts_listbox.insert(tk.END, display_text)
            self.contacts_listbox.itemconfig(
                len(self.contacts_listbox.get(0, tk.END)) - 1,
                user_data=contact.contact_id
            )
    
    def _on_add_contact(self):
        """Handle add contact button"""
        dialog = AddContactDialog(self)
        if dialog.result:
            name, host, port = dialog.result
            
            contact = self.controller.contact_provider.add_contact_manual(name, host, port)
            if contact:
                self.add_contact(contact)
                messagebox.showinfo(
                    "Success",
                    f"Contact '{name}' added!\n\n"
                    f"To connect, they need to be online.\n"
                    f"You can also share your IP and port ({port}) with them."
                )
            else:
                messagebox.showerror("Error", "Failed to add contact")
    
    def _on_contact_double_click(self, event):
        """Handle double-click on contact"""
        selection = self.contacts_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        item_data = self.contacts_listbox.item(index)
        
        # Get contact ID from item data (stored via tags or separate dict)
        # For simplicity, we'll look up by name
        display_text = self.contacts_listbox.get(index)
        contact_name = display_text.split(' ', 1)[1] if ' ' in display_text else display_text
        
        # Find contact
        contacts = self.controller.contact_provider.get_all_contacts()
        for contact in contacts:
            if contact.name == contact_name:
                self.controller.open_chat(contact.contact_id)
                break
    
    def add_contact(self, contact):
        """Add a contact to the list"""
        status_icon = "🟢" if contact.is_online() else "⚫"
        display_text = f"{status_icon} {contact.name}"
        
        self.contacts_listbox.insert(tk.END, display_text)
        self.status_label.config(text=f"Added: {contact.name}")
    
    def remove_contact(self, contact_id: str):
        """Remove a contact from the list"""
        contacts = self.controller.contact_provider.get_all_contacts()
        for i, contact in enumerate(contacts):
            if contact.contact_id == contact_id:
                self.contacts_listbox.delete(i)
                self.status_label.config(text=f"Removed contact")
                break
    
    def update_contact(self, contact):
        """Update a contact in the list"""
        self._load_contacts()  # Reload all for simplicity


class AddContactDialog(simpledialog.Dialog):
    """Dialog for adding a new contact"""
    
    def __init__(self, parent):
        self.result = None
        super().__init__(parent, "Add Contact")
    
    def body(self, master):
        """Create dialog body"""
        ttk.Label(master, text="Contact Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(master, width=30)
        self.name_entry.grid(row=0, column=1, pady=5)
        
        ttk.Label(master, text="IP Address or Hostname:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.host_entry = ttk.Entry(master, width=30)
        self.host_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(master, text="Port:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.port_entry = ttk.Entry(master, width=30)
        self.port_entry.insert(0, "37021")
        self.port_entry.grid(row=2, column=1, pady=5)
        
        # Info label
        info_label = ttk.Label(
            master,
            text="Enter the IP address and port of the person you want to chat with.\n"
                 "They must be running P2P Messenger and have port forwarding set up\n"
                 "if connecting over the internet.",
            wraplength=350,
            justify=tk.LEFT,
            font=('Helvetica', 9),
            foreground='#666666'
        )
        info_label.grid(row=3, column=0, columnspan=2, pady=(15, 0))
        
        return self.name_entry  # Initial focus
    
    def apply(self):
        """Handle OK button"""
        name = self.name_entry.get().strip()
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()
        
        if not name or not host:
            messagebox.showerror("Error", "Please fill in all fields", parent=self)
            return
        
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Port must be between 1 and 65535", parent=self)
            return
        
        self.result = (name, host, port)
