"""Vulture whitelist for framework hook methods and dynamic protocol fields.

This file is parsed by vulture to mark known false positives as "used".
It is not imported by application runtime code.
"""

# ruff: noqa: B018, F821

# Qt / PyQtGraph framework override hooks.
tickStrings
paint
boundingRect
dataBounds
highlightBlock

# Stable-Baselines callback hooks.
_on_step
_on_rollout_end

# BaseHTTPRequestHandler hook.
do_GET
log_message
forward

# Training/evaluation helpers referenced indirectly.
last_mean_reward
_profile_policy
_holding_cost_rate
_load_optuna_defaults
_format_metric_value

# UI state kept for widget lifecycle / layout management.
_details_splitter
_optuna_best_summary_grid
_reward_group

# Protobuf / cTrader dynamic fields accessed by attribute name.
_.accessToken
_.clientId
_.clientSecret
_.orderType
_.relativeStopLoss
_.relativeTakeProfit
_.slippageInPoints
_.subscribeToSpotTimestamp
_.observation_space
_._syntax_highlighter
