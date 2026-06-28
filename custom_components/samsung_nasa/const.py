# 통합 상수 정의
"""Constants for the samsung_nasa integration."""

DOMAIN = "samsung_nasa"

CONF_HOST = "host"
CONF_PORT = "port"

DEFAULT_PORT = 8899  # EW11 default transparent TCP port

# Control retransmission. Samsung indoor units BEEP on every received command,
# so each resend = an extra beep. Control reliably lands on the first send via
# EW11, and the unit's status Notifications arrive in multi-second bursts (so a
# blind 1s retry fires before the unit can reply, causing a double beep).
# Therefore retransmission is OFF by default. Set SEND_MAX_RETRIES > 0 to
# re-enable it; notify-as-ack then stops the resends once the unit replies.
SEND_RETRY_INTERVAL = 1.0  # seconds between resends of a pending command
SEND_MAX_RETRIES = 0
RECONNECT_INTERVAL = 5.0  # seconds between reconnect attempts

# Dispatcher signals
SIGNAL_DEVICE_DISCOVERED = f"{DOMAIN}_device_discovered"
SIGNAL_STATE_UPDATED = f"{DOMAIN}_state_updated"

# NASA address classes we surface as entities
KLASS_INDOOR = 0x20
KLASS_OUTDOOR = 0x10
