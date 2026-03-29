from can_interface import parse_can_frame


def read_steering_input(frame_bytes, delta_ms):
    frame = parse_can_frame(frame_bytes, delta_ms)
    return frame["payload"][0] if frame["payload"] else 0


def read_brake_pedal_signal(frame_bytes, delta_ms):
    frame = parse_can_frame(frame_bytes, delta_ms)
    return frame["payload"][1] if len(frame["payload"]) > 1 else 0


def read_accelerator_signal(frame_bytes, delta_ms):
    frame = parse_can_frame(frame_bytes, delta_ms)
    return frame["payload"][2] if len(frame["payload"]) > 2 else 0


def diagnostic_health_check_interval(frame_bytes, delta_ms):
    frame = parse_can_frame(frame_bytes, delta_ms)
    return not frame["stale"]
