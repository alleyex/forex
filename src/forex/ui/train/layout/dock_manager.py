from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QDockWidget, QMainWindow, QWidget


@dataclass
class DockSet:
    log: QDockWidget
    training_params: QDockWidget
    simulation_params: QDockWidget


class DockManager:
    _TRAINING_DOCK_DEFAULT_WIDTH = 700
    _SIMULATION_DOCK_DEFAULT_WIDTH = 520

    def __init__(
        self,
        main_window: QMainWindow,
        log_panel: QWidget,
        training_params_panel: QWidget,
        simulation_params_panel: QWidget,
    ) -> None:
        self._main_window = main_window
        self._dock_set = DockSet(
            log=self._create_log_dock(log_panel),
            training_params=self._create_training_params_dock(training_params_panel),
            simulation_params=self._create_simulation_params_dock(simulation_params_panel),
        )
        self._configure_corners()

    @property
    def docks(self) -> DockSet:
        return self._dock_set

    def add_docks(self) -> None:
        self._main_window.addDockWidget(Qt.BottomDockWidgetArea, self._dock_set.log)
        self._main_window.addDockWidget(Qt.LeftDockWidgetArea, self._dock_set.training_params)
        self._main_window.addDockWidget(Qt.LeftDockWidgetArea, self._dock_set.simulation_params)
        QTimer.singleShot(0, self._apply_initial_dock_sizes)

    def set_log_collapsed(self, collapsed: bool) -> None:
        log_dock = self._dock_set.log
        log_panel = log_dock.widget()
        if log_panel is not None:
            log_panel.setVisible(not collapsed)
        if collapsed:
            log_dock.setMinimumHeight(28)
            log_dock.setMaximumHeight(32)
        else:
            log_dock.setMinimumHeight(180)
            log_dock.setMaximumHeight(16777215)

    def set_panel_mode(self, mode: str) -> None:
        if mode == "training":
            self._dock_set.training_params.setVisible(True)
            self._dock_set.simulation_params.setVisible(False)
            self._resize_left_dock(
                self._dock_set.training_params,
                self._TRAINING_DOCK_DEFAULT_WIDTH,
            )
        elif mode == "simulation":
            self._dock_set.training_params.setVisible(False)
            self._dock_set.simulation_params.setVisible(True)
            self._resize_left_dock(
                self._dock_set.simulation_params,
                self._SIMULATION_DOCK_DEFAULT_WIDTH,
            )
        else:
            self._dock_set.training_params.setVisible(False)
            self._dock_set.simulation_params.setVisible(False)

    def _create_log_dock(self, panel: QWidget) -> QDockWidget:
        dock = QDockWidget("", self._main_window)
        dock.setObjectName("log_dock")
        dock.setWidget(panel)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setMinimumHeight(180)
        return dock

    def _create_training_params_dock(self, panel: QWidget) -> QDockWidget:
        dock = QDockWidget("", self._main_window)
        dock.setObjectName("training_params_dock")
        dock.setTitleBarWidget(QWidget(dock))
        dock.setWidget(panel)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        dock.setVisible(False)
        return dock

    def _create_simulation_params_dock(self, panel: QWidget) -> QDockWidget:
        dock = QDockWidget("", self._main_window)
        dock.setObjectName("simulation_params_dock")
        dock.setTitleBarWidget(QWidget(dock))
        dock.setWidget(panel)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        dock.setVisible(False)
        return dock

    def _configure_corners(self) -> None:
        self._main_window.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self._main_window.setCorner(Qt.BottomRightCorner, Qt.BottomDockWidgetArea)

    def _apply_initial_dock_sizes(self) -> None:
        if self._dock_set.training_params.isVisible():
            self._resize_left_dock(
                self._dock_set.training_params,
                self._TRAINING_DOCK_DEFAULT_WIDTH,
            )
        if self._dock_set.simulation_params.isVisible():
            self._resize_left_dock(
                self._dock_set.simulation_params,
                self._SIMULATION_DOCK_DEFAULT_WIDTH,
            )

    def _resize_left_dock(self, dock: QDockWidget, width: int) -> None:
        if not dock.isVisible():
            return
        try:
            self._main_window.resizeDocks([dock], [max(320, int(width))], Qt.Horizontal)
        except Exception:
            pass


class DockManagerController(QObject):
    def __init__(
        self,
        *,
        parent: QMainWindow,
        log_panel: QWidget,
        training_params_panel: QWidget,
        simulation_params_panel: QWidget,
        on_log_visibility_changed: callable | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = DockManager(
            parent,
            log_panel=log_panel,
            training_params_panel=training_params_panel,
            simulation_params_panel=simulation_params_panel,
        )
        self._manager.add_docks()
        self._on_log_visibility_changed = on_log_visibility_changed
        self.log_dock.visibilityChanged.connect(self._handle_log_visibility_changed)

    @property
    def manager(self) -> DockManager:
        return self._manager

    @property
    def log_dock(self) -> QDockWidget:
        return self._manager.docks.log

    def set_log_collapsed(self, collapsed: bool) -> None:
        self._manager.set_log_collapsed(collapsed)

    def _handle_log_visibility_changed(self, visible: bool) -> None:
        if self._on_log_visibility_changed:
            self._on_log_visibility_changed(visible)
