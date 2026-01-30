from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from ui_train.controllers import ToolbarController
from ui_train.layout.dock_manager import DockManagerController
from ui_train.layout.panel_switcher import PanelSet, PanelSwitcher
from ui_train.presenters import SimulationPresenter, TrainingPresenter
from ui_train.state import HistoryDownloadState, SimulationState, TrainingState
from ui_train.widgets.log_widget import LogWidget
from ui_train.widgets.simulation_panel import SimulationPanel, SimulationParamsPanel
from ui_train.widgets.trade_panel import TradePanel
from ui_train.widgets.training_panel import TrainingPanel, TrainingParamsPanel


@dataclass
class PanelBundle:
    trade_panel: TradePanel
    training_panel: TrainingPanel
    training_params_panel: TrainingParamsPanel
    simulation_panel: SimulationPanel
    simulation_params_panel: SimulationParamsPanel
    log_panel: LogWidget
    training_state: TrainingState
    training_presenter: TrainingPresenter
    simulation_state: SimulationState
    simulation_presenter: SimulationPresenter
    history_download_state: HistoryDownloadState


@dataclass
class StackBundle:
    stack: QStackedWidget
    trade_container: QWidget


@dataclass
class StatusBundle:
    app_auth_label: QLabel
    oauth_label: QLabel


@dataclass
class ToolbarBundle:
    toolbar_controller: ToolbarController
    action_toggle_connection: object


def build_panels(
    parent: QWidget,
    *,
    on_optuna_best_params: Callable[[dict], None],
    on_simulation_summary: Callable[[dict], None],
) -> PanelBundle:
    trade_panel = TradePanel()
    training_panel = TrainingPanel()
    training_params_panel = TrainingParamsPanel()
    simulation_panel = SimulationPanel()
    simulation_params_panel = SimulationParamsPanel()

    log_panel = LogWidget(
        title="",
        with_timestamp=True,
        monospace=True,
        font_point_delta=2,
    )

    training_state = TrainingState(parent=parent)
    training_presenter = TrainingPresenter(parent=parent, state=training_state)
    training_state.metric_point.connect(training_panel.append_metric_point)
    training_state.optuna_point.connect(training_panel.append_optuna_point)
    training_state.optuna_reset.connect(training_params_panel.reset_optuna_results)
    training_state.optuna_trial_summary.connect(training_params_panel.update_optuna_trial_summary)
    training_state.optuna_best_params.connect(training_params_panel.update_optuna_best_params)
    training_state.best_params_found.connect(on_optuna_best_params)
    training_state.log_message.connect(log_panel.append)

    simulation_state = SimulationState(parent=parent)
    simulation_presenter = SimulationPresenter(parent=parent, state=simulation_state)
    simulation_state.reset_plot.connect(simulation_panel.reset_plot)
    simulation_state.flush_plot.connect(simulation_panel.flush_plot)
    simulation_state.reset_summary.connect(simulation_params_panel.reset_summary)
    simulation_state.equity_point.connect(simulation_panel.append_equity_point)
    simulation_state.summary_update.connect(on_simulation_summary)
    simulation_state.trade_stats.connect(simulation_params_panel.update_trade_stats)
    simulation_state.streak_stats.connect(simulation_params_panel.update_streak_stats)
    simulation_state.holding_stats.connect(simulation_params_panel.update_holding_stats)
    simulation_state.action_distribution.connect(simulation_params_panel.update_action_distribution)
    simulation_state.playback_range.connect(simulation_params_panel.update_playback_range)
    simulation_state.log_message.connect(log_panel.append)

    history_download_state = HistoryDownloadState(parent=parent)
    history_download_state.log_message.connect(log_panel.append)

    return PanelBundle(
        trade_panel=trade_panel,
        training_panel=training_panel,
        training_params_panel=training_params_panel,
        simulation_panel=simulation_panel,
        simulation_params_panel=simulation_params_panel,
        log_panel=log_panel,
        training_state=training_state,
        training_presenter=training_presenter,
        simulation_state=simulation_state,
        simulation_presenter=simulation_presenter,
        history_download_state=history_download_state,
    )


def build_stack(
    main_window: QMainWindow,
    *,
    trade_panel: TradePanel,
    training_panel: TrainingPanel,
    simulation_panel: SimulationPanel,
) -> StackBundle:
    stack = QStackedWidget()
    trade_container = QWidget()
    trade_layout = QHBoxLayout(trade_container)
    trade_layout.setContentsMargins(10, 10, 10, 10)
    trade_layout.setSpacing(10)
    trade_layout.addWidget(trade_panel)

    stack.addWidget(trade_container)
    stack.addWidget(training_panel)
    stack.addWidget(simulation_panel)
    main_window.setCentralWidget(stack)
    return StackBundle(stack=stack, trade_container=trade_container)


def build_docks(
    main_window: QMainWindow,
    *,
    log_panel: LogWidget,
    training_params_panel: TrainingParamsPanel,
    simulation_params_panel: SimulationParamsPanel,
) -> DockManagerController:
    return DockManagerController(
        parent=main_window,
        log_panel=log_panel,
        training_params_panel=training_params_panel,
        simulation_params_panel=simulation_params_panel,
    )


def build_panel_switcher(
    *,
    stack: QStackedWidget,
    trade_container: QWidget,
    training_panel: TrainingPanel,
    simulation_panel: SimulationPanel,
    dock_controller: DockManagerController,
) -> PanelSwitcher:
    return PanelSwitcher(
        stack=stack,
        panels=PanelSet(
            trade=trade_container,
            training=training_panel,
            simulation=simulation_panel,
        ),
        dock_manager=dock_controller.manager,
    )


def build_status_bar(
    main_window: QMainWindow,
    *,
    app_auth_text: str,
    oauth_text: str,
) -> StatusBundle:
    status_bar = main_window.statusBar()
    app_auth_label = QLabel(app_auth_text)
    oauth_label = QLabel(oauth_text)
    status_bar.addWidget(app_auth_label)
    status_bar.addWidget(oauth_label)
    return StatusBundle(app_auth_label=app_auth_label, oauth_label=oauth_label)


def build_toolbar(
    main_window: QMainWindow,
    *,
    dock_controller: DockManagerController,
    on_app_auth: Callable[[], None],
    on_oauth: Callable[[], None],
    on_toggle_connection: Callable[[], None],
    on_fetch_account_info: Callable[[], None],
    on_train_ppo: Callable[[], None],
    on_simulation: Callable[[], None],
    on_history_download: Callable[[], None],
    on_toggle_log: Callable[[bool], None],
) -> ToolbarBundle:
    toolbar_controller = ToolbarController(
        parent=main_window,
        log_visible=dock_controller.log_dock.isVisible(),
        on_app_auth=on_app_auth,
        on_oauth=on_oauth,
        on_toggle_connection=on_toggle_connection,
        on_fetch_account_info=on_fetch_account_info,
        on_train_ppo=on_train_ppo,
        on_simulation=on_simulation,
        on_history_download=on_history_download,
        on_toggle_log=on_toggle_log,
    )
    dock_controller.bind_log_action(toolbar_controller.action_toggle_log)
    return ToolbarBundle(
        toolbar_controller=toolbar_controller,
        action_toggle_connection=toolbar_controller.action_toggle_connection,
    )
