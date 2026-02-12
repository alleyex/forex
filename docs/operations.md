# Operations Guide

## Quick Start

```bash
QT_OPENGL=software LOG_LEVEL=INFO python main_train.py
```

For live trading UI:

```bash
QT_OPENGL=software LOG_LEVEL=INFO python main_live.py
```

## Common Environment Variables

- `TOKEN_FILE`: token file path (default `token.json`)
- `BROKER_PROVIDER`: provider name (default `ctrader`)
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- `LOG_FILE`: optional file path for logs
- `CTRADER_REQUEST_TIMEOUT`: seconds
- `CTRADER_OAUTH_TIMEOUT`: seconds
- `CTRADER_OAUTH_LOGIN_TIMEOUT`: seconds
- `CTRADER_RETRY_MAX_ATTEMPTS`: integer, 0 disables retries
- `CTRADER_RETRY_BACKOFF_SECONDS`: seconds
- `METRICS_LOG_INTERVAL`: metrics snapshot interval

## Metrics

A lightweight metrics registry logs snapshots at `METRICS_LOG_INTERVAL` seconds.
Examples of counters and observations:

- `ctrader.app_auth.success`
- `ctrader.oauth.timeout`
- `ctrader.account_list.latency_s`
- `ctrader.symbol_list.retry`

Metrics are emitted through the `metrics` logger. Adjust log level or direct output via `LOG_FILE`.

## Live UI Log Event Catalog

Live UI logs use this normalized format:

`[LEVEL] event_name | key=value | key=value`

Supported event names:

- `request_history`: sent recent-history request (`account_id`, `symbol_id`)
- `history_requested`: broker history fetch window (`timeframe`, `count`, `from`, `to`)
- `history_loaded`: candles loaded into chart/model window (`candles`)
- `unhandled_message`: unknown payload from broker (`payload_type`)
- `invalid_request`: broker invalid-request detail (`detail`)
- `funds_received`: account funds/summary update
- `heartbeat_sent`: heartbeat sent to broker
- `quotes_subscribed`: quote subscription sent (`symbols`)
- `symbol_details_request`: symbol metadata request started
- `symbol_details_received`: symbol metadata response received
- `order_executed`: order/close execution result
- `decision_input`: model inference inputs (`tf`, `candles`, `features`, `action`, `target`)
- `decision_normalized`: post-threshold/step normalized decision (`desired`, `step`)
- `strategy_state`: strategy state snapshot (`side`, `open_same`, `cap`, etc.)
- `same_side_capped`: same-side add blocked by cap
- `same_side_add_allowed`: same-side add allowed
- `same_side_hold_near_full`: near-full hold blocked extra add
- `cost_check`: estimated edge vs transaction cost (`edge_bps`, `cost_bps`)
- `volume_scaling`: lot scaling by signal strength (`base_lot`, `scaled_lot`)
- `place_order`: order placement request payload
- `close_position`: close request payload
- `signal_throttled`: min-interval throttle status (`wait_s`)

Fallback behavior:

- If a structured log line matches `event | key=value` but `event` is not in the catalog, it will be normalized as:
  - `unknown_event | raw_event=<original> | key=value ...`

## Troubleshooting

### Import Errors

If you see module import errors, confirm you are running from repo root and the `src/` layout is intact.

### PySide6 Issues

Make sure PySide6 is installed:

```bash
pip install -e '.[ui]'
```

### OAuth Login Timeout

If OAuth login is timing out, increase:

```bash
export CTRADER_OAUTH_LOGIN_TIMEOUT=600
```

### Retry Behavior

Retries are disabled by default. Enable with:

```bash
export CTRADER_RETRY_MAX_ATTEMPTS=3
export CTRADER_RETRY_BACKOFF_SECONDS=2
```
