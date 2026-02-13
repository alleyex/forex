import os
import sys
from importlib import resources

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from forex.app.bootstrap import bootstrap
from forex.ui.live.main_window import LiveMainWindow


def main() -> int:
    """Live trading app entry point"""
    use_cases, _, event_bus, app_state = bootstrap()
    if os.getenv("QT_OPENGL") is None:
        os.environ["QT_OPENGL"] = "software"
    if os.getenv("QT_QUICK_BACKEND") is None:
        os.environ["QT_QUICK_BACKEND"] = "software"
    QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    style_path = resources.files("forex.ui.shared.styles").joinpath("app.qss")
    if style_path.is_file():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))

    main_window = LiveMainWindow(
        use_cases=use_cases,
        event_bus=event_bus,
        app_state=app_state,
    )
    main_window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
