from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QStackedWidget, QWidget

from forex.ui.train.layout.dock_manager import DockManager


@dataclass
class PanelSet:
    trade: QWidget
    training: QWidget
    simulation: QWidget
    data_check: QWidget


class PanelSwitcher:
    def __init__(
        self,
        stack: QStackedWidget,
        panels: PanelSet,
        dock_manager: DockManager,
    ) -> None:
        self._stack = stack
        self._panels = panels
        self._dock_manager = dock_manager

    def show(self, panel: str) -> None:
        if panel in {"training", "optuna"}:
            self._stack.setCurrentWidget(self._panels.training)
            self._dock_manager.set_panel_mode("training")
            self._dock_manager.docks.log.setVisible(False)
        elif panel == "simulation":
            self._stack.setCurrentWidget(self._panels.simulation)
            self._dock_manager.set_panel_mode("simulation")
            self._dock_manager.docks.log.setVisible(False)
        elif panel == "data_check":
            self._stack.setCurrentWidget(self._panels.data_check)
            self._dock_manager.set_panel_mode("trade")
            self._dock_manager.docks.log.setVisible(True)
            self._dock_manager.set_log_collapsed(False)
        else:
            self._stack.setCurrentWidget(self._panels.trade)
            self._dock_manager.set_panel_mode("trade")
            self._dock_manager.docks.log.setVisible(True)
            self._dock_manager.set_log_collapsed(False)
