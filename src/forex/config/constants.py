from enum import IntEnum

class MessageType(IntEnum):
    """cTrader Open API Message Types"""
    HEARTBEAT = 51
    APP_AUTH_RESPONSE = 2101
    ERROR_RESPONSE = 2142
    ACCOUNT_AUTH_RESPONSE = 2103


class ConnectionStatus(IntEnum):
    """Connection state machine"""
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    APP_AUTHENTICATED = 3
    ACCOUNT_AUTHENTICATED = 4