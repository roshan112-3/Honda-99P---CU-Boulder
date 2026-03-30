def read_brake_fluid_pressure(raw_adc):
    return raw_adc * 0.5


def map_pedal_input(raw_value):
    return max(0.0, min(raw_value / 1023.0, 1.0))
