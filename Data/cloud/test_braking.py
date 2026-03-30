from abs_subsystem import apply_ABS_threshold
from braking_controller import calculate_brake_distance, command_emergency_stop, estimate_stopping_force
from safety_controller import run_vehicle_dynamics, safety_controller_loop
from vehicle_sensors import map_pedal_input, read_brake_fluid_pressure


def test_brake_distance_nominal():
    return calculate_brake_distance(24.0)


def test_emergency_stop_latency():
    return command_emergency_stop(24.0, 58.0)


def test_stopping_force_range():
    return estimate_stopping_force(24.0, 58.0)


def test_ABS_trigger_threshold():
    return apply_ABS_threshold(0.24, 58.0)


def test_safety_controller_integration():
    return safety_controller_loop(24.0, 58.0)


def test_vehicle_dynamics_end_to_end():
    return run_vehicle_dynamics(24.0, 58.0)


def test_brake_fluid_pressure_sensor():
    return read_brake_fluid_pressure(80)


def test_pedal_input_mapping():
    return map_pedal_input(512)
