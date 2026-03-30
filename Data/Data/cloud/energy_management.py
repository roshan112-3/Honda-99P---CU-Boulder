def battery_charge_cycle(cell_voltage_v, pack_current_a):
    return cell_voltage_v * pack_current_a


def regen_braking_efficiency(speed_mps, battery_soc):
    return speed_mps * (1.0 - min(battery_soc, 0.95))
