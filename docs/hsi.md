# Hardware-Software Interface (HSI) - v1.0

Overview
--------
This HSI describes the telemetry packets, CAN IDs, sampling rates, and ADC characteristics used by the on-board sensors and the firmware interface to the cloud ingestion service.

Packet definitions (v1):
- SENSOR_PKT (CAN ID 0x180): 8 bytes
  - byte0: version (1)
  - byte1: sensor_id
  - byte2-3: temperature_raw (16-bit, signed)
  - byte4-5: pressure_raw (16-bit, unsigned)
  - byte6: status_flags
  - byte7: checksum (simple sum & 0xFF)

Packet definitions (v1.1):
- SENSOR_PKT (CAN ID 0x200): 10 bytes (version 2)
  - byte0: version (2)
  - byte1: sensor_id
  - byte2-3: temperature_raw (16-bit, signed)
  - byte4-5: pressure_raw (16-bit, unsigned)
  - byte6-7: humidity_raw (16-bit, unsigned)
  - byte8: status_flags
  - byte9: checksum (simple sum & 0xFF)

Sampling and ADC
----------------
- ADC resolution: 12 bits
- Default sensor sampling rate: 100 Hz
- CAN bus: 500000 bps

Interrupts
----------
- IRQ_ADC: triggered on ADC conversion complete
- IRQ_CAN_RX: triggered when a CAN frame is received

Change log
----------
- v1.0 - initial baseline
 - v1.1 - added humidity field in SENSOR_PKT (version 2) and extended packet length to 10 bytes; CAN ID updated to 0x200
