# main_train.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import qInstallMessageHandler
import traceback

from bootstrap import bootstrap
from ui_train.main_window import MainWindow


def _qt_message_handler(mode, context, message) -> None:
    location = f"{context.file}:{context.line}" if context.file else "<unknown>"
    print(f"Qt[{mode}] {message} ({location})")
    if "QObject::startTimer" in message:
        print("Python stack (most recent call last):")
        print("".join(traceback.format_stack()))


def main() -> int:
    """Application entry point"""
    use_cases, _, event_bus, app_state = bootstrap()
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Consistent cross-platform look
    style_path = Path("ui_train/styles/app.qss")
    if style_path.exists():
        app.setStyleSheet(style_path.read_text())
    
    main_window = MainWindow(
        use_cases=use_cases,
        event_bus=event_bus,
        app_state=app_state,
    )
    main_window.showMaximized()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
