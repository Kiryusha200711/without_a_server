"""
P2P Messenger - Main Entry Point
"""

import sys
import os
import traceback
import tkinter as tk
from tkinter import messagebox

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.app import P2PMessengerApp


def setup_excepthook():
    """Setup global exception hook"""
    original_excepthook = sys.excepthook
    
    def custom_excepthook(exc_type, exc_value, exc_traceback):
        # Log the exception
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"Unhandled exception:\n{error_msg}")
        
        # Show error dialog if possible
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Critical Error",
                f"An unexpected error occurred:\n\n{str(exc_value)}\n\nThe application will now close."
            )
            root.destroy()
        except:
            pass
        
        # Call original handler
        original_excepthook(exc_type, exc_value, exc_traceback)
    
    sys.excepthook = custom_excepthook


def main():
    """Main entry point"""
    # Setup exception handling
    setup_excepthook()
    
    # Create and run application
    try:
        app = P2PMessengerApp()
        app.run()
    except Exception as e:
        print(f"Failed to start application: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
