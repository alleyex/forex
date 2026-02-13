from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QStyle,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forex.ui.live.widgets.decision_inspector_widget import DecisionInspectorWidget


class LiveUIBuilder:
    """Builds heavy UI sections for LiveMainWindow."""

    def __init__(self, window) -> None:
        self._window = window

    def build_autotrade_panel(self) -> QWidget:
        panel = QGroupBox("Auto Trading")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tabs = self._create_tabs(layout)
        _model_tab, model_tab_layout, form_model = self._create_tab_form(tabs, "Model Lab", object_name="modelTab")
        _basic_tab, _basic_tab_layout, form_basic = self._create_tab_form(tabs, "Basic", object_name="basicTab")
        _trade_tab, _trade_tab_layout, form_trade = self._create_tab_form(tabs, "Trade", object_name="tradeTab")
        _adv_tab, _adv_tab_layout, form_adv = self._create_tab_form(tabs, "Advanced", object_name="advancedTab")

        self._apply_tabs_style(tabs)
        self._build_model_tab(form_model=form_model, model_tab_layout=model_tab_layout, panel=panel)
        self._build_basic_tab(form_basic=form_basic)
        self._build_trade_tab(form_trade=form_trade, panel=panel)
        self._build_advanced_tab(form_adv=form_adv)

        return panel

    def _create_tabs(self, parent_layout: QVBoxLayout) -> QTabWidget:
        w = self._window
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.setUsesScrollButtons(False)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setDrawBase(False)
        parent_layout.addWidget(tabs)
        w._autotrade_tabs = tabs
        return tabs

    def _create_tab_form(
        self, tabs: QTabWidget, title: str, object_name: str | None = None
    ) -> tuple[QWidget, QVBoxLayout, QFormLayout]:
        w = self._window
        tab = QWidget()
        if object_name:
            tab.setObjectName(object_name)
        if object_name == "basicTab":
            w._basic_tab = tab
        if object_name == "tradeTab":
            w._trade_tab = tab
        if object_name == "advancedTab":
            w._advanced_tab = tab
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(12, 10, 18, 24)
        tab_layout.setSpacing(8)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        tab_layout.addLayout(form)
        tab_layout.addStretch(1)
        tabs.addTab(tab, title)
        return tab, tab_layout, form

    @staticmethod
    def _create_card(
        title: str,
        *,
        title_align: str = "left",
        title_tone: str = "default",
    ) -> tuple[QGroupBox, QFormLayout]:
        card = QGroupBox(title)
        card.setObjectName("card")
        card.setProperty("titleAlign", title_align)
        card.setProperty("titleTone", title_tone)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        card_form = QFormLayout()
        card_form.setHorizontalSpacing(16)
        card_form.setVerticalSpacing(10)
        card_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        card_form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        card_form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        card_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        card_layout.addLayout(card_form)
        return card, card_form

    def _apply_tabs_style(self, tabs: QTabWidget) -> None:
        w = self._window
        tabs_style = """
            QTabWidget::pane {
                border: none;
                top: 0px;
                }
            QTabWidget::tab-bar {
                left: 0px;
            }
            QTabBar::base {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                margin: 0px;
            }
            QTabBar::tab:!selected {
                margin-top: 0px;
            }
            QWidget#modelTab QLabel[section="true"],
            QWidget#basicTab QLabel[section="true"],
            QWidget#tradeTab QLabel[section="true"],
            QWidget#advancedTab QLabel[section="true"] {
                color: #a8b1bc;
                font-weight: 600;
                letter-spacing: 0.5px;
                padding-top: 6px;
                padding-bottom: 2px;
            }
            QWidget#modelTab QLabel,
            QWidget#basicTab QLabel,
            QWidget#tradeTab QLabel,
            QWidget#advancedTab QLabel {
                color: #d3d8e0;
            }
            QWidget#modelTab QLabel[spacer="true"],
            QWidget#basicTab QLabel[spacer="true"],
            QWidget#tradeTab QLabel[spacer="true"],
            QWidget#advancedTab QLabel[spacer="true"] {
                min-height: 10px;
                min-width: 0px;
            }
            QWidget#modelTab QLabel[section="true"],
            QWidget#basicTab QLabel[section="true"],
            QWidget#tradeTab QLabel[section="true"],
            QWidget#advancedTab QLabel[section="true"] {
                color: #9aa6b2;
                min-width: 0px;
            }
            QWidget#modelTab QFrame[divider="true"],
            QWidget#basicTab QFrame[divider="true"],
            QWidget#tradeTab QFrame[divider="true"],
            QWidget#advancedTab QFrame[divider="true"] {
                border: none;
                border-top: 1px solid #343c46;
                margin-top: 6px;
                margin-bottom: 6px;
            }
            QWidget#modelTab QComboBox,
            QWidget#modelTab QDoubleSpinBox,
            QWidget#modelTab QSpinBox,
            QWidget#modelTab QLineEdit,
            QWidget#basicTab QComboBox,
            QWidget#basicTab QDoubleSpinBox,
            QWidget#basicTab QSpinBox,
            QWidget#basicTab QLineEdit,
            QWidget#tradeTab QComboBox,
            QWidget#tradeTab QDoubleSpinBox,
            QWidget#tradeTab QSpinBox,
            QWidget#tradeTab QLineEdit,
            QWidget#advancedTab QComboBox,
            QWidget#advancedTab QDoubleSpinBox,
            QWidget#advancedTab QSpinBox,
            QWidget#advancedTab QLineEdit {
                min-height: 30px;
                padding: 2px 8px;
            }
            QWidget#modelTab QRadioButton,
            QWidget#modelTab QCheckBox,
            QWidget#basicTab QRadioButton,
            QWidget#basicTab QCheckBox,
            QWidget#tradeTab QRadioButton,
            QWidget#tradeTab QCheckBox,
            QWidget#advancedTab QRadioButton,
            QWidget#advancedTab QCheckBox {
                spacing: 8px;
            }
            QWidget#modelTab QRadioButton::indicator,
            QWidget#modelTab QCheckBox::indicator,
            QWidget#basicTab QRadioButton::indicator,
            QWidget#basicTab QCheckBox::indicator,
            QWidget#tradeTab QRadioButton::indicator,
            QWidget#tradeTab QCheckBox::indicator,
            QWidget#advancedTab QRadioButton::indicator,
            QWidget#advancedTab QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QWidget#modelTab QGroupBox#card,
            QWidget#basicTab QGroupBox#card,
            QWidget#tradeTab QGroupBox#card,
            QWidget#advancedTab QGroupBox#card {
                background: #262d36;
                border: 1px solid #343c46;
                border-radius: 10px;
                margin-top: 6px;
            }
            QWidget#basicTab QGroupBox#card::title,
            QWidget#tradeTab QGroupBox#card::title,
            QWidget#advancedTab QGroupBox#card::title {
                color: #cdd6e1;
                font-weight: 500;
                letter-spacing: 0.2px;
                padding: 0px 8px;
                background: #262d36;
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
            }
            QWidget#modelTab QGroupBox#card::title {
                color: #cdd6e1;
                font-weight: 500;
                letter-spacing: 0.2px;
                padding: 0px 8px;
                background: #262d36;
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
            }
            QWidget#modelTab QGroupBox#card[titleTone="line"]::title,
            QWidget#basicTab QGroupBox#card[titleTone="line"]::title,
            QWidget#tradeTab QGroupBox#card[titleTone="line"]::title,
            QWidget#advancedTab QGroupBox#card[titleTone="line"]::title {
                color: __CARD_LINE_TITLE_COLOR__;
                font-weight: 300;
                font-size: __CARD_LINE_TITLE_FONT_SIZE_PX__px;
                subcontrol-origin: margin;
                subcontrol-position: top right;
                left: __CARD_LINE_TITLE_OFFSET_PX__px;
            }
            QWidget#modelTab QGroupBox#card QLineEdit,
            QWidget#modelTab QGroupBox#card QComboBox,
            QWidget#modelTab QGroupBox#card QDoubleSpinBox,
            QWidget#modelTab QGroupBox#card QSpinBox {
                background: #1f252d;
                border: 1px solid #343c46;
                border-radius: 8px;
            }
            QWidget#basicTab QGroupBox#card QLineEdit,
            QWidget#basicTab QGroupBox#card QComboBox,
            QWidget#basicTab QGroupBox#card QDoubleSpinBox,
            QWidget#basicTab QGroupBox#card QSpinBox {
                background: #1f252d;
                border: 1px solid #343c46;
                border-radius: 8px;
            }
            QWidget#modelTab QGroupBox#card QPushButton,
            QWidget#modelTab QGroupBox#card QToolButton {
                min-height: 30px;
            }
            QWidget#modelTab QToolButton#modelBrowseIcon {
                background: transparent;
                border: none;
                padding: 2px;
            }
            QWidget#modelTab QToolButton#modelBrowseIcon:hover {
                background: rgba(255, 255, 255, 0.10);
                border-radius: 4px;
            }
            QWidget#modelTab QToolButton#modelBrowseIcon:pressed {
                background: rgba(255, 255, 255, 0.16);
                border-radius: 4px;
            }
            """
        tabs_style = tabs_style.replace("__CARD_LINE_TITLE_COLOR__", w._CARD_LINE_TITLE_COLOR)
        tabs_style = tabs_style.replace(
            "__CARD_LINE_TITLE_FONT_SIZE_PX__", str(w._CARD_LINE_TITLE_FONT_SIZE_PX)
        )
        tabs_style = tabs_style.replace("__CARD_LINE_TITLE_OFFSET_PX__", str(w._CARD_LINE_TITLE_OFFSET_PX))
        tabs.setStyleSheet(tabs_style)

    def _build_model_tab(self, *, form_model: QFormLayout, model_tab_layout: QVBoxLayout, panel: QWidget) -> None:
        w = self._window
        model_row = QWidget()
        model_layout = QVBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(6)
        model_field_row = QWidget()
        model_field_layout = QHBoxLayout(model_field_row)
        model_field_layout.setContentsMargins(0, 0, 0, 0)
        model_field_layout.setSpacing(6)
        w._model_path = QLineEdit("ppo-forex.zip")
        w._model_path.setPlaceholderText("ppo-forex.zip")
        w._browse_model_dir_button = QToolButton()
        browse_icon = QIcon.fromTheme("folder-open")
        if browse_icon.isNull():
            browse_icon = QIcon.fromTheme("document-open")
        if browse_icon.isNull():
            browse_icon = w.style().standardIcon(QStyle.SP_DirOpenIcon)
        if browse_icon.isNull():
            browse_icon = w.style().standardIcon(QStyle.SP_FileIcon)
        w._browse_model_dir_button.setIcon(browse_icon)
        w._browse_model_dir_button.setIconSize(QSize(18, 18))
        w._browse_model_dir_button.setToolTip("Select model file")
        w._browse_model_dir_button.setObjectName("modelBrowseIcon")
        w._browse_model_dir_button.setText("")
        w._browse_model_dir_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        w._browse_model_dir_button.setAutoRaise(True)
        w._browse_model_dir_button.setStyleSheet(
            """
            QToolButton {
                background: transparent;
                border: none;
                padding: 2px;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 0.10);
                border-radius: 4px;
            }
            QToolButton:pressed {
                background: rgba(255, 255, 255, 0.16);
                border-radius: 4px;
            }
            """
        )
        field_height = 34
        w._model_path.setMinimumHeight(field_height)
        w._browse_model_dir_button.setMinimumHeight(field_height)
        w._browse_model_dir_button.clicked.connect(w._browse_model_file)
        model_field_layout.addWidget(w._model_path, 1)
        model_field_layout.addWidget(w._browse_model_dir_button)
        model_layout.addWidget(model_field_row)

        w._auto_trade_toggle = QCheckBox("Enable")
        w._auto_trade_toggle.toggled.connect(w._toggle_auto_trade)
        auto_trade_row = QWidget()
        auto_trade_layout = QHBoxLayout(auto_trade_row)
        auto_trade_layout.setContentsMargins(0, 0, 0, 0)
        auto_trade_layout.setSpacing(8)
        auto_trade_layout.addWidget(w._auto_trade_toggle)
        w._auto_start_status = QLabel("Loading model...")
        w._auto_start_status.setStyleSheet("color:#9aa6b2; font-weight:500;")
        w._auto_start_status.setVisible(False)
        auto_trade_layout.addWidget(w._auto_start_status)
        auto_trade_layout.addStretch(1)

        model_card, model_card_form = self._create_card("Model Lab", title_tone="line")
        model_card_form.addRow("Model file", model_row)
        model_card_form.addRow("Auto Trade", auto_trade_row)
        form_model.addRow(model_card)

        w._auto_log_panel = DecisionInspectorWidget(
            title="Auto Trade",
            with_timestamp=True,
            max_entries=200,
        )
        w._auto_log_panel.setMinimumHeight(340)
        w._auto_log_panel.setMaximumHeight(16777215)
        model_tab_layout.addWidget(w._auto_log_panel)

    def _build_basic_tab(self, *, form_basic: QFormLayout) -> None:
        w = self._window
        w._trade_symbol = QComboBox()
        w._sync_trade_symbol_choices(preferred_symbol=w._symbol_name)
        symbol_row = QWidget()
        symbol_layout = QHBoxLayout(symbol_row)
        symbol_layout.setContentsMargins(0, 0, 0, 0)
        symbol_layout.setSpacing(6)
        symbol_layout.addWidget(w._trade_symbol)
        basic_card, basic_card_form = self._create_card("Basic Settings", title_tone="line")
        basic_card_form.addRow("Symbol", symbol_row)
        w._trade_symbol.currentTextChanged.connect(w._handle_trade_symbol_changed)

        w._trade_timeframe = QComboBox()
        w._trade_timeframe.addItems(["M1", "M5", "M15", "M30", "H1", "H4"])
        basic_card_form.addRow("Timeframe", w._trade_timeframe)
        w._trade_timeframe.currentTextChanged.connect(w._handle_trade_timeframe_changed)
        form_basic.addRow(basic_card)

    def _build_trade_tab(self, *, form_trade: QFormLayout, panel: QWidget) -> None:
        w = self._window
        trade_card, trade_card_form = self._create_card("Position Sizing", title_tone="line")
        lot_row = QWidget()
        lot_layout = QVBoxLayout(lot_row)
        lot_layout.setContentsMargins(0, 0, 0, 0)
        lot_layout.setSpacing(4)
        w._lot_fixed = QRadioButton("Fixed lot")
        w._lot_risk = QRadioButton("Risk %")
        w._lot_fixed.setChecked(True)
        lot_group = QButtonGroup(panel)
        lot_group.addButton(w._lot_fixed)
        lot_group.addButton(w._lot_risk)
        lot_layout.addWidget(w._lot_fixed)
        lot_layout.addWidget(w._lot_risk)
        trade_card_form.addRow("Sizing", lot_row)

        w._lot_value = QDoubleSpinBox()
        w._lot_value.setDecimals(2)
        w._lot_value.setRange(0.01, 100.0)
        w._lot_value.setSingleStep(0.01)
        w._lot_value.setValue(0.1)
        w._lot_value.setSuffix(" lots")
        trade_card_form.addRow("Lot / Risk%", w._lot_value)
        w._lot_fixed.toggled.connect(w._sync_lot_value_style)
        w._lot_risk.toggled.connect(w._sync_lot_value_style)
        w._sync_lot_value_style()

        w._max_positions = QSpinBox()
        w._max_positions.setRange(1, 20)
        w._max_positions.setValue(1)
        trade_card_form.addRow("Max positions", w._max_positions)
        form_trade.addRow(trade_card)

        risk_card, risk_card_form = self._create_card("Risk Controls", title_tone="line")
        w._stop_loss = QDoubleSpinBox()
        w._stop_loss.setDecimals(0)
        w._stop_loss.setRange(0.0, 1000000.0)
        w._stop_loss.setSingleStep(10.0)
        w._stop_loss.setValue(500.0)
        w._stop_loss.setSuffix(" pt")
        risk_card_form.addRow("Stop loss (points)", w._stop_loss)

        w._take_profit = QDoubleSpinBox()
        w._take_profit.setDecimals(0)
        w._take_profit.setRange(0.0, 1000000.0)
        w._take_profit.setSingleStep(10.0)
        w._take_profit.setValue(800.0)
        w._take_profit.setSuffix(" pt")
        risk_card_form.addRow("Take profit (points)", w._take_profit)

        w._risk_guard = QCheckBox("Enable")
        risk_card_form.addRow("Risk guard", w._risk_guard)

        w._max_drawdown = QDoubleSpinBox()
        w._max_drawdown.setDecimals(1)
        w._max_drawdown.setRange(0.0, 100.0)
        w._max_drawdown.setSingleStep(0.5)
        w._max_drawdown.setValue(10.0)
        w._max_drawdown.setSuffix(" %")
        risk_card_form.addRow("Max DD %", w._max_drawdown)

        w._daily_loss = QDoubleSpinBox()
        w._daily_loss.setDecimals(1)
        w._daily_loss.setRange(0.0, 100.0)
        w._daily_loss.setSingleStep(0.5)
        w._daily_loss.setValue(5.0)
        w._daily_loss.setSuffix(" %")
        risk_card_form.addRow("Daily loss %", w._daily_loss)
        form_trade.addRow(risk_card)

    def _build_advanced_tab(self, *, form_adv: QFormLayout) -> None:
        w = self._window
        advanced_card, advanced_card_form = self._create_card("Advanced Settings", title_tone="line")
        w._min_signal_interval = QSpinBox()
        w._min_signal_interval.setRange(0, 3600)
        w._min_signal_interval.setValue(5)
        advanced_card_form.addRow("Min interval (s)", w._min_signal_interval)

        w._slippage_bps = QDoubleSpinBox()
        w._slippage_bps.setDecimals(2)
        w._slippage_bps.setRange(0.0, 50.0)
        w._slippage_bps.setValue(0.5)
        advanced_card_form.addRow("Slippage bps", w._slippage_bps)

        w._fee_bps = QDoubleSpinBox()
        w._fee_bps.setDecimals(2)
        w._fee_bps.setRange(0.0, 50.0)
        w._fee_bps.setValue(1.0)
        advanced_card_form.addRow("Fee bps", w._fee_bps)

        w._confidence = QDoubleSpinBox()
        w._confidence.setDecimals(2)
        w._confidence.setRange(0.0, 1.0)
        w._confidence.setSingleStep(0.05)
        w._confidence.setValue(0.0)
        advanced_card_form.addRow("Confidence", w._confidence)

        w._position_step = QDoubleSpinBox()
        w._position_step.setDecimals(2)
        w._position_step.setRange(0.0, 1.0)
        w._position_step.setSingleStep(0.05)
        w._position_step.setValue(0.0)
        advanced_card_form.addRow("Position step", w._position_step)

        w._near_full_hold = QCheckBox("Enable")
        w._near_full_hold.setChecked(True)
        advanced_card_form.addRow("Near-full hold", w._near_full_hold)

        w._same_side_rebalance = QCheckBox("Enable")
        w._same_side_rebalance.setChecked(False)
        advanced_card_form.addRow("Same-side rebalance", w._same_side_rebalance)

        w._scale_lot_by_signal = QCheckBox("Enable")
        w._scale_lot_by_signal.setChecked(False)
        advanced_card_form.addRow("Scale lot by signal", w._scale_lot_by_signal)

        w._auto_debug = QCheckBox("Enable")
        advanced_card_form.addRow("Debug logs", w._auto_debug)
        w._quote_affects_chart = QCheckBox("Enable")
        w._quote_affects_chart.setChecked(bool(getattr(w, "_quote_affects_chart_candles", False)))
        w._quote_affects_chart.toggled.connect(w._set_quote_chart_mode)
        advanced_card_form.addRow("Quotes affect candles", w._quote_affects_chart)
        form_adv.addRow(advanced_card)
