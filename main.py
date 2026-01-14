# main.py
import sys
from PySide6.QtWidgets import QApplication

from ui.dialogs.app_auth_dialog import AppAuthDialog
from ui.dialogs.oauth_dialog import OAuthDialog
from ui.main_window import MainWindow


def main() -> int:
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Consistent cross-platform look
    
    # Show authentication dialog
    auth_dialog = AppAuthDialog(token_file="token.json", auto_connect=True)
    
    if auth_dialog.exec() != AppAuthDialog.Accepted:
        return 0
    
    # Get authenticated app service before OAuth
    service = auth_dialog.get_service()

    oauth_dialog = OAuthDialog(
        token_file="token.json",
        auto_connect=True,
        app_auth_service=service,
    )
    if oauth_dialog.exec() != OAuthDialog.Accepted:
        return 0

    # Get authenticated services and show main window
    oauth_service = oauth_dialog.get_service()
    
    main_window = MainWindow(service=service, oauth_service=oauth_service)
    main_window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
