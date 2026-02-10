from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer


def initialize_live_window_state(window) -> None:
    window._connection_controller = None
    window._history_service = None
    window._history_requested = False
    window._pending_history = False
    window._last_history_request_key = None
    window._last_history_request_ts = 0.0
    window._last_history_success_key = None
    window._last_history_success_ts = 0.0
    window._trendbar_service = None
    window._trendbar_active = False
    window._order_service = None
    window._auto_enabled = False
    window._auto_model = None
    window._auto_feature_scaler = None
    window._auto_position = 0.0
    window._auto_position_id = None
    window._auto_last_action_ts = None
    window._auto_balance = None
    window._auto_peak_balance = None
    window._auto_day_balance = None
    window._auto_day_key = None
    window._auto_log_panel = None
    window._positions_table = None
    window._positions_message_handler = None
    window._account_summary_labels = {}
    window._position_pnl_by_id = {}
    window._accounts = []
    window._account_combo = None
    window._account_refresh_button = None
    window._account_switch_in_progress = False
    window._last_authorized_account_id = None
    window._unauthorized_accounts = set()
    window._pending_full_reconnect = False
    window._account_funds_uc = None
    window._symbol_list_uc = None
    window._symbol_by_id_uc = None
    window._last_funds_fetch_ts = 0.0
    window._candles = []
    window._chart_plot = None
    window._candlestick_item = None
    window._last_price_line = None
    window._last_price_label = None
    window._project_root = Path(__file__).resolve().parents[2]
    window._symbol_names, window._symbol_id_map = window._load_symbol_catalog()
    window._symbol_id_to_name = {symbol_id: name for name, symbol_id in window._symbol_id_map.items()}
    window._symbol_volume_constraints = {}
    window._symbol_volume_loaded = False
    window._symbol_details_by_id = {}
    window._symbol_digits_by_name = {}
    window._symbol_overrides = {}
    window._symbol_overrides_loaded = False
    window._symbol_details_unavailable = set()
    window._fx_symbols = window._filter_fx_symbols(window._symbol_names)
    window._symbol_name = _default_symbol_name(window)
    window._symbol_id = window._resolve_symbol_id(window._symbol_name)
    window._timeframe = "M1"
    window._price_digits = 5
    window._chart_ready = False
    window._pending_candles = None
    window._chart_frozen = True

    window._chart_timer = QTimer(window)
    window._chart_timer.setInterval(200)
    window._chart_timer.timeout.connect(window._flush_chart_update)
    window._chart_timer.start()

    window._funds_timer = QTimer(window)
    window._funds_timer.setInterval(5000)
    window._funds_timer.timeout.connect(window._refresh_account_balance)

    window._positions_refresh_timer = QTimer(window)
    window._positions_refresh_timer.setSingleShot(True)
    window._positions_refresh_timer.setInterval(300)
    window._positions_refresh_timer.timeout.connect(window._apply_positions_refresh)
    window._positions_refresh_pending = False

    window._auto_connect_timer = QTimer(window)
    window._auto_connect_timer.setSingleShot(True)
    window._auto_connect_timer.timeout.connect(window._toggle_connection)

    window._autotrade_settings_path = Path("data/auto_trade_settings.json")
    window._autotrade_loading = False
    window._quotes_table = None
    window._max_quote_rows = 2
    window._quote_symbols = window._default_quote_symbols()
    window._quote_digits = {
        "EURUSD": 5,
        "USDJPY": 3,
    }
    window._quote_symbol_ids = {name: window._resolve_symbol_id(name) for name in window._quote_symbols}
    window._quote_rows = {}
    window._quote_row_digits = {}
    window._quote_last_mid = {}
    window._quote_last_bid = {}
    window._quote_last_ask = {}
    window._quote_subscribed = False
    window._quote_subscribed_ids = set()
    window._quote_subscribe_inflight = set()
    window._spot_message_handler = None
    window._open_positions = []
    window._pending_symbol_list = None


def _default_symbol_name(window) -> str:
    if "EURUSD" in window._symbol_id_map:
        return "EURUSD"
    if window._fx_symbols:
        return window._fx_symbols[0]
    return "EURUSD"
