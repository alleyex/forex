import sys
from PySide6.QtWidgets import QApplication

from ui.dialogs.app_auth_dialog import AppAuthDialog
from ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = AppAuthDialog()
    if dlg.exec() != AppAuthDialog.Accepted:
        sys.exit(0)

    main = MainWindow()
    main.show()

    sys.exit(app.exec())


