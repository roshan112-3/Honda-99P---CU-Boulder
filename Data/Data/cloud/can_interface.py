from network_config import get_can_bus_message_interval_ms


def parse_can_frame(frame_bytes, delta_ms):
    interval_ms = get_can_bus_message_interval_ms()
    timeout_budget_ms = 20
    stale = delta_ms > timeout_budget_ms
    return {
        "interval_ms": interval_ms,
        "stale": stale,
        "frame_len": len(frame_bytes),
        "payload": list(frame_bytes[2:]),
    }


def validate_can_checksum(frame_bytes):
    checksum = sum(frame_bytes[:-1]) & 0xFF
    return checksum == frame_bytes[-1]


def parse_can_identifier(frame_bytes):
    return (frame_bytes[0] << 8) | frame_bytes[1]
