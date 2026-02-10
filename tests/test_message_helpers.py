from __future__ import annotations

from forex.infrastructure.broker.ctrader.services.message_helpers import (
    is_non_subscribed_trendbar_unsubscribe,
)


def test_is_non_subscribed_trendbar_unsubscribe_matches_expected_error() -> None:
    assert is_non_subscribed_trendbar_unsubscribe(
        "INVALID_REQUEST",
        "Try to unsubscribe to a non-subscribed period of Trendbars for symbolId:1",
    )


def test_is_non_subscribed_trendbar_unsubscribe_rejects_other_errors() -> None:
    assert not is_non_subscribed_trendbar_unsubscribe(
        "INVALID_REQUEST",
        "Some other invalid request",
    )
