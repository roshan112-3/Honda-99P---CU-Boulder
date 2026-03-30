from braking_controller import command_emergency_stop


def safety_controller_loop(speed_mps, brake_pressure_bar):
    stop_plan = command_emergency_stop(speed_mps, brake_pressure_bar)
    return stop_plan["distance_m"] < 70.0 and stop_plan["force_n"] > 1200.0


def run_vehicle_dynamics(speed_mps, brake_pressure_bar):
    return {
        "safe": safety_controller_loop(speed_mps, brake_pressure_bar),
        "speed_mps": speed_mps,
    }
