# main_train.py
import sys
from importlib import resources
from pathlib import Path
import traceback

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import qInstallMessageHandler

from bootstrap import bootstrap
from ui.train.main_window import MainWindow


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
    style_path = resources.files("ui.shared.styles").joinpath("app.qss")
    if style_path.is_file():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))
    
    main_window = MainWindow(
        use_cases=use_cases,
        event_bus=event_bus,
        app_state=app_state,
    )
    main_window.showMaximized()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
