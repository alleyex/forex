import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import qInstallMessageHandler
import traceback

from bootstrap import bootstrap
from ui.dialogs.app_auth_dialog import AppAuthDialog
from ui.main_window import MainWindow
from config import load_config


def _qt_message_handler(mode, context, message) -> None:
    location = f"{context.file}:{context.line}" if context.file else "<unknown>"
    print(f"Qt[{mode}] {message} ({location})")
    if "QObject::startTimer" in message:
        print("Python stack (most recent call last):")
        print("".join(traceback.format_stack()))


if __name__ == "__main__":
    use_cases, _, event_bus, app_state = bootstrap()
    config = load_config()
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    dlg = AppAuthDialog(
        token_file=config.token_file,
        use_cases=use_cases,
        event_bus=event_bus,
        app_state=app_state,
    )
    if dlg.exec() != AppAuthDialog.Accepted:
        sys.exit(0)

    main = MainWindow(use_cases=use_cases, event_bus=event_bus, app_state=app_state)
    main.show()

    sys.exit(app.exec())
