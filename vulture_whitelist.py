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
