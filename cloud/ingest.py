"""
Cloud ingestion service simulation.
Receives telemetry payloads (binary), validates, normalizes and writes to storage.
"""
import threading
import queue
import time
import struct
import json
import random

class Ingestor:
    def __init__(self):
        self.q = queue.Queue()
        self.running = False
        self.storage = []

    def start(self):
        self.running = True
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    def stop(self):
        self.running = False

    def push_raw(self, raw_bytes):
        # raw_bytes: bytes
        self.q.put(raw_bytes)

    def _worker(self):
        while self.running:
            try:
                raw = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                parsed = self.parse_sensor_packet(raw)
                self.storage.append(parsed)
                print("Ingested:", parsed)
            except Exception as e:
                print("Parse error:", e)

    def parse_sensor_packet(self, raw):
        # Expect 8 bytes based on HSI v1
        if len(raw) < 8:
            raise ValueError("packet too short")
        # Unpack: B B h H B B
        version, sensor_id, temp_raw, pressure_raw, status_flags, checksum = struct.unpack('>BBhHBB', raw)
        # Validate checksum (simple sum & 0xFF)
        calc = (sum(raw[:7]) & 0xFF)
        if checksum != calc:
            raise ValueError(f"checksum mismatch {checksum} != {calc}")
        data = {
            'version': version,
            'sensor_id': sensor_id,
            'temperature_raw': temp_raw,
            'pressure_raw': pressure_raw,
            'status_flags': status_flags,
            'timestamp': time.time()
        }
        # Normalize values
        data['temperature_c'] = (temp_raw / 16.0)  # scaling used by firmware
        data['pressure_hpa'] = pressure_raw
        return data

def main_demo():
    ing = Ingestor()
    ing.start()
    # simulate incoming frames
    for i in range(20):
        temp = int((25 + random.uniform(-1,1)) * 16)
        pres = int(1013 + random.randint(-2,2))
        pkt = struct.pack('>BBhHBB', 1, 1, temp, pres, 0, 0)
        chk = sum(pkt[:7]) & 0xFF
        pkt = pkt[:7] + bytes([chk])
        ing.push_raw(pkt)
        time.sleep(0.05)
    time.sleep(1)
    ing.stop()

if __name__ == '__main__':
    main_demo()
