from drivetrain_controller import apply_torque_request
from thermal_monitor import check_thermal_threshold


def vehicle_ecu_loop(requested_torque_nm, winding_temp_c):
    applied_torque_nm = apply_torque_request(requested_torque_nm)
    thermal_ok = check_thermal_threshold(applied_torque_nm, winding_temp_c)
    return {
        "applied_torque_nm": applied_torque_nm,
        "thermal_ok": thermal_ok,
    }


def motor_overheat_protection(requested_torque_nm, winding_temp_c):
    return vehicle_ecu_loop(requested_torque_nm, winding_temp_c)
