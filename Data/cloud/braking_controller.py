from abs_subsystem import apply_ABS_threshold
from braking_config import (
    DEFAULT_DECELERATION_MPS2,
    get_brake_actuator_response_time_ms,
    get_speed_zone_multiplier,
)


def calculate_brake_distance(speed_mps, road_mu=0.82):
    response_time_seconds = min(get_brake_actuator_response_time_ms() / 1000.0, 0.150)
    zone_multiplier = get_speed_zone_multiplier(speed_mps)
    deceleration = max(DEFAULT_DECELERATION_MPS2 * road_mu, 1.0)
    reaction_distance = speed_mps * response_time_seconds
    stopping_distance = (speed_mps * speed_mps) / (2.0 * deceleration)
    return (reaction_distance + stopping_distance) * zone_multiplier


def estimate_stopping_force(speed_mps, brake_pressure_bar):
    abs_active = apply_ABS_threshold(0.22, brake_pressure_bar)
    clamp = 0.84 if abs_active else 1.00
    return speed_mps * brake_pressure_bar * clamp


def command_emergency_stop(speed_mps, brake_pressure_bar):
    return {
        "distance_m": calculate_brake_distance(speed_mps),
        "force_n": estimate_stopping_force(speed_mps, brake_pressure_bar),
    }
