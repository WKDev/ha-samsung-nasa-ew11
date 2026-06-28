# 통합 상수 정의
"""Constants for the samsung_nasa integration."""

DOMAIN = "samsung_nasa"

CONF_HOST = "host"
CONF_PORT = "port"

DEFAULT_PORT = 8899  # EW11 default transparent TCP port

# Control retransmission (Samsung indoor units do not Ack; resend until the
# target replies — see context-notes.md "notify-as-ack").
SEND_RETRY_INTERVAL = 1.0  # seconds between resends of a pending command
SEND_MAX_RETRIES = 5
RECONNECT_INTERVAL = 5.0  # seconds between reconnect attempts

# Dispatcher signals
SIGNAL_DEVICE_DISCOVERED = f"{DOMAIN}_device_discovered"
SIGNAL_STATE_UPDATED = f"{DOMAIN}_state_updated"

# NASA address classes we surface as entities
KLASS_INDOOR = 0x20
KLASS_OUTDOOR = 0x10
