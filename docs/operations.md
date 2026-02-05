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
