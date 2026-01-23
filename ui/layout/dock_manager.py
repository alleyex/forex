from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow, QWidget


@dataclass
class DockSet:
    log: QDockWidget
    training_params: QDockWidget
    simulation_params: QDockWidget


class DockManager:
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

    def toggle_log(self, visible: bool) -> None:
        self.set_log_collapsed(not visible)
        self._dock_set.log.setVisible(True)

    def set_panel_mode(self, mode: str) -> None:
        if mode == "training":
            self._dock_set.training_params.setVisible(True)
            self._dock_set.simulation_params.setVisible(False)
        elif mode == "simulation":
            self._dock_set.training_params.setVisible(False)
            self._dock_set.simulation_params.setVisible(True)
        else:
            self._dock_set.training_params.setVisible(False)
            self._dock_set.simulation_params.setVisible(False)

    def _create_log_dock(self, panel: QWidget) -> QDockWidget:
        dock = QDockWidget("", self._main_window)
        dock.setObjectName("log_dock")
        dock.setWidget(panel)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        dock.setMinimumHeight(180)
        return dock

    def _create_training_params_dock(self, panel: QWidget) -> QDockWidget:
        dock = QDockWidget("PPO 參數設定", self._main_window)
        dock.setObjectName("training_params_dock")
        dock.setWidget(panel)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        dock.setVisible(False)
        return dock

    def _create_simulation_params_dock(self, panel: QWidget) -> QDockWidget:
        dock = QDockWidget("回放參數", self._main_window)
        dock.setObjectName("simulation_params_dock")
        dock.setWidget(panel)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        dock.setVisible(False)
        return dock

    def _configure_corners(self) -> None:
        self._main_window.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self._main_window.setCorner(Qt.BottomRightCorner, Qt.BottomDockWidgetArea)
