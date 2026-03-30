from drivetrain_controller import apply_torque_request
from ecu_manager import motor_overheat_protection, vehicle_ecu_loop
from energy_management import battery_charge_cycle, regen_braking_efficiency


def test_torque_application_limits():
    return apply_torque_request(335)


def test_thermal_cutoff_trigger():
    return vehicle_ecu_loop(335, 108.0)


def test_ecu_integration_nominal():
    return vehicle_ecu_loop(320, 102.0)


def test_motor_overheat_protection():
    return motor_overheat_protection(335, 108.0)


def test_battery_charge_cycle():
    return battery_charge_cycle(3.9, 12.0)


def test_regen_braking_efficiency():
    return regen_braking_efficiency(18.0, 0.45)
