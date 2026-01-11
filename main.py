# main.py
import sys
from PySide6.QtWidgets import QApplication

from ui.dialogs.app_auth_dialog import AppAuthDialog
from ui.main_window import MainWindow


def main() -> int:
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Consistent cross-platform look
    
    # Show authentication dialog
    auth_dialog = AppAuthDialog(token_file="token.json")
    
    if auth_dialog.exec() != AppAuthDialog.Accepted:
        return 0
    
    # Get authenticated service and show main window
    service = auth_dialog.get_service()
    
    main_window = MainWindow(service=service)
    main_window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())