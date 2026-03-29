import struct

def pack_sensor_packet(version, sensor_id, temp_raw, pressure_raw, status_flags):
    pkt = struct.pack('>BBhHBB', version, sensor_id, temp_raw, pressure_raw, status_flags, 0)
    chk = sum(pkt[:7]) & 0xFF
    return pkt[:7] + bytes([chk])
