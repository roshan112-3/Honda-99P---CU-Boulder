def check_thermal_threshold(applied_torque_nm, winding_temp_c):
    thermal_reference_torque_nm = 280
    thermal_load = winding_temp_c + ((applied_torque_nm / thermal_reference_torque_nm) * 28.0)
    return thermal_load < 130.0
