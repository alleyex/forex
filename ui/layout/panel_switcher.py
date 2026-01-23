from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import QStackedWidget, QWidget

from ui.layout.dock_manager import DockManager


@dataclass
class PanelSet:
    trade: QWidget
    training: QWidget
    simulation: QWidget


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

    def show(self, panel: str, show_log: Optional[bool]) -> None:
        if panel == "training":
            self._stack.setCurrentWidget(self._panels.training)
            self._dock_manager.set_panel_mode("training")
        elif panel == "simulation":
            self._stack.setCurrentWidget(self._panels.simulation)
            self._dock_manager.set_panel_mode("simulation")
        else:
            self._stack.setCurrentWidget(self._panels.trade)
            self._dock_manager.set_panel_mode("trade")

        if show_log is None:
            return

        if show_log:
            self._dock_manager.docks.log.setVisible(True)
            self._dock_manager.set_log_collapsed(False)
        else:
            self._dock_manager.docks.log.setVisible(False)
