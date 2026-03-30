from drivetrain_config import get_max_motor_torque_nm


def apply_torque_request(requested_nm):
    ceiling = get_max_motor_torque_nm()
    return min(requested_nm, ceiling)
