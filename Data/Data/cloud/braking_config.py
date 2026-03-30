BRAKE_ACTUATOR_RESPONSE_TIME_MS = 200
DEFAULT_DECELERATION_MPS2 = 8.4

SPEED_ZONE_LOOKUP = (
    (0.0, 13.4, 1.00),
    (13.4, 22.3, 1.05),
    (22.3, 31.3, 1.11),
    (31.3, 100.0, 1.18),
)


def get_brake_actuator_response_time_ms():
    return BRAKE_ACTUATOR_RESPONSE_TIME_MS


def get_speed_zone_multiplier(speed_mps):
    for lower, upper, multiplier in SPEED_ZONE_LOOKUP:
        if lower <= speed_mps < upper:
            return multiplier
    return SPEED_ZONE_LOOKUP[-1][2]
