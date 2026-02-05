"""
Application bootstrap: set up logging and resolve the broker provider.
"""
from typing import Optional, Tuple

from application.events import EventBus
from application.state import AppState
from application.broker.use_cases import BrokerUseCases
from broker.core.provider import get_provider, register_provider
from infrastructure.broker.ctrader.provider import CTraderProvider
from config.logging import setup_logging
from config.runtime import load_config
from infrastructure.broker.fake.provider import FakeProvider


def bootstrap(provider_name: Optional[str] = None) -> Tuple[BrokerUseCases, str, EventBus, AppState]:
    """
    Initialize shared infrastructure and return broker use-cases facade.

    Args:
        provider_name: Optional provider name; defaults to DEFAULT_PROVIDER.

    Returns:
        (use_cases, provider_name)
    """
    config = load_config()
    setup_logging(level_name=config.log_level, log_file=config.log_file)
    name = provider_name or config.provider
    register_provider(CTraderProvider())
    register_provider(FakeProvider())
    provider = get_provider(name)
    use_cases = BrokerUseCases(provider)
    event_bus = EventBus()
    app_state = AppState()
    return use_cases, name, event_bus, app_state


__all__ = ["bootstrap"]
