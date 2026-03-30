from braking_config import get_brake_actuator_response_time_ms


def apply_ABS_threshold(wheel_slip_ratio, brake_pressure_bar):
    response_time_ms = get_brake_actuator_response_time_ms()
    threshold = 0.18
    if response_time_ms <= 160:
        threshold += 0.02
    return wheel_slip_ratio >= threshold and brake_pressure_bar >= 42.0
