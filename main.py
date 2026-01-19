# main.py
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import qInstallMessageHandler
import traceback

from bootstrap import bootstrap
from ui.dialogs.app_auth_dialog import AppAuthDialog
from ui.dialogs.oauth_dialog import OAuthDialog
from ui.main_window import MainWindow
from config import load_config


def _qt_message_handler(mode, context, message) -> None:
    location = f"{context.file}:{context.line}" if context.file else "<unknown>"
    print(f"Qt[{mode}] {message} ({location})")
    if "QObject::startTimer" in message:
        print("Python stack (most recent call last):")
        print("".join(traceback.format_stack()))


def main() -> int:
    """Application entry point"""
    use_cases, _, event_bus, app_state = bootstrap()
    config = load_config()
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Consistent cross-platform look
    
    # Show authentication dialog
    auth_dialog = AppAuthDialog(
        token_file=config.token_file,
        auto_connect=True,
        use_cases=use_cases,
        event_bus=event_bus,
        app_state=app_state,
    )
    
    if auth_dialog.exec() != AppAuthDialog.Accepted:
        return 0
    
    # Get authenticated app service before OAuth
    service = auth_dialog.get_service()

    oauth_dialog = OAuthDialog(
        token_file=config.token_file,
        auto_connect=True,
        app_auth_service=service,
        use_cases=use_cases,
        event_bus=event_bus,
        app_state=app_state,
    )
    if oauth_dialog.exec() != OAuthDialog.Accepted:
        return 0

    # Get authenticated services and show main window
    oauth_service = oauth_dialog.get_service()
    
    main_window = MainWindow(
        service=service,
        oauth_service=oauth_service,
        use_cases=use_cases,
        event_bus=event_bus,
        app_state=app_state,
    )
    main_window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
