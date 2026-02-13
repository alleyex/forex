from __future__ import annotations

from pathlib import Path

from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATradeSide

from forex.ml.rl.features.feature_builder import load_scaler


class LiveAutoRuntimeService:
    """Handles auto-trade runtime bootstrapping (model + order service)."""

    def __init__(self, window) -> None:
        self._window = window

    def load_auto_model(self) -> bool:
        w = self._window
        raw_path = w._model_path.text().strip()
        if not raw_path:
            w._auto_log("⚠️ Model path is empty")
            return False
        model_path = w._resolve_model_path(raw_path)
        if not model_path.exists():
            w._auto_log(f"⚠️ Model file not found: {model_path}")
            return False
        path = str(model_path)
        try:
            import importlib
            import sys
            import typing

            # PySide6 can inject typing.Self on Python 3.10 which breaks torch.
            if hasattr(typing, "Self"):
                delattr(typing, "Self")
            if "typing_extensions" in sys.modules:
                importlib.reload(sys.modules["typing_extensions"])
        except Exception:
            pass
        try:
            from stable_baselines3 import PPO
        except Exception as exc:
            w._auto_log(f"❌ Failed to import PPO: {exc}")
            return False
        try:
            w._auto_model = PPO.load(path)
        except Exception as exc:
            hint = ""
            if "typing.Self" in str(exc):
                hint = " (try Python>=3.10 or stable-baselines3<=2.3.x)"
            w._auto_log(f"❌ Failed to load model: {exc}{hint}")
            return False
        w._auto_feature_scaler = None
        scaler_path = model_path.with_suffix(".scaler.json")
        if scaler_path.exists():
            try:
                w._auto_feature_scaler = load_scaler(scaler_path)
                w._auto_log(f"✅ Feature scaler loaded: {scaler_path.name}")
            except Exception as exc:
                w._auto_log(f"⚠️ Failed to load feature scaler: {exc}")
        else:
            w._auto_log("⚠️ Feature scaler not found; using raw features")
        w._auto_log(f"✅ Model loaded: {Path(path).name}")
        return True

    def ensure_order_service(self) -> None:
        w = self._window
        if w._order_service or not w._service:
            return
        w._order_service = w._use_cases.create_order_service(w._service)
        if w._app_state:
            scope = w._app_state.selected_account_scope
            set_scope = getattr(w._order_service, "set_permission_scope", None)
            if callable(set_scope):
                set_scope(scope)
        w._order_service.set_callbacks(
            on_execution=self.handle_order_execution,
            on_error=lambda e: w._auto_log(f"❌ Order error: {e}"),
            on_log=w._auto_log,
        )

    def handle_order_execution(self, payload: dict) -> None:
        w = self._window
        position_id = payload.get("position_id")
        if position_id:
            w._auto_position_id = int(position_id)
        order = payload.get("order")
        position = payload.get("position")
        deal = payload.get("deal")
        symbol_id = (
            getattr(order, "symbolId", None)
            or getattr(position, "symbolId", None)
            or getattr(deal, "symbolId", None)
        )
        symbol_name = w._symbol_id_to_name.get(int(symbol_id)) if symbol_id else None
        volume = (
            getattr(order, "volume", None)
            or getattr(position, "volume", None)
            or getattr(deal, "volume", None)
        )
        if not volume:
            volume = payload.get("requested_volume")
        lot = None
        volume_text = None
        if volume is not None:
            try:
                volume_value = float(volume)
                lot = w._volume_to_lots(volume_value)
                volume_text = f"{int(volume_value)}"
            except (TypeError, ValueError):
                lot = None
        trade_side = getattr(order, "tradeSide", None)
        if trade_side == ProtoOATradeSide.BUY:
            side_text = "BUY"
        elif trade_side == ProtoOATradeSide.SELL:
            side_text = "SELL"
        else:
            side_text = None
        parts = []
        if side_text:
            parts.append(side_text)
        if lot is not None:
            parts.append(f"{lot:.3f} lot")
        if volume_text:
            parts.append(f"(volume {volume_text})")
        if symbol_name:
            parts.append(symbol_name)
        if position_id:
            parts.append(f"(pos {position_id})")
        if parts:
            w._auto_log(f"✅ Order executed: {' '.join(parts)}")
        w._request_positions()

