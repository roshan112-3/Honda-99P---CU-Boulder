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

- Encryption
----------
- status_flags bit 7 (0x80) indicates the payload (bytes 0..n-2) is XOR-encrypted with a single-byte key. Checksum is computed over the post-encryption bytes. Cloud must detect the flag and decrypt using the agreed key (0x5A) before interpreting numeric fields.

Checksum Algorithm
------------------
- v2.1: SENSOR_PKT checksum moved from simple sum to CRC-8 (poly 0x07, initial 0x00) computed over bytes 0..n-2 (post-encryption if present). Cloud and firmware MUST implement CRC-8 to validate v2.1 packets.

Sampling and ADC
----------------
- ADC resolution: 14 bits (firmware and cloud must adjust scaling of temperature representation)
- Default sensor sampling rate: 50 Hz
 - CAN bus: 1000000 bps

Heartbeat
---------
- HEARTBEAT_PKT (CAN ID 0x300): 2 bytes
  - byte0: opcode (0xAA)
  - byte1: status (0x00 = ok)
  - Interval: 1000ms

Interrupts
----------
- IRQ_ADC: triggered on ADC conversion complete (priority 2)
- IRQ_CAN_RX: triggered when a CAN frame is received (priority 3)

Interrupt priorities: lower number -> higher priority. Firmware should support registering handlers with explicit priority to ensure timely handling of ADC data.

Change log
----------
- v1.0 - initial baseline
 - v1.1 - added humidity field in SENSOR_PKT (version 2) and extended packet length to 10 bytes; CAN ID updated to 0x200
 - v2.1 - switched checksum to CRC-8
 - v1.2 - extended SENSOR_PKT to include fuel_level (version 3) -> 12 bytes
 - v1.3 - added firmware fault-injection hooks for testing and CI
 - v2.1 - switched checksum to CRC-8
 - v1.2 - extended SENSOR_PKT to include fuel_level (version 3) -> 12 bytes

Packet definitions (v3):
- SENSOR_PKT (CAN ID 0x200): 12 bytes (version 3)
  - byte0: version (3)
  - byte1: sensor_id
  - byte2-3: temperature_raw (16-bit, signed)
  - byte4-5: pressure_raw (16-bit, unsigned)
  - byte6-7: humidity_raw (16-bit, unsigned)
  - byte8-9: fuel_raw (16-bit, unsigned)
  - byte10: status_flags
  - byte11: checksum (CRC-8)
