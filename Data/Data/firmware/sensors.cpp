#include "sensors.h"
#include <cstdlib>
#include <ctime>
#include <iostream>
#include <cstddef>

static uint8_t crc8(const uint8_t *data, size_t len)
{
    uint8_t crc = 0x00;
    const uint8_t poly = 0x07;
    for (size_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (int b = 0; b < 8; ++b) {
            if (crc & 0x80) crc = (uint8_t)((crc << 1) ^ poly);
            else crc <<= 1;
        }
    }
    return crc;
}

SensorManager::SensorManager()
    : sampling_rate_hz(50), adc_resolution_bits(14), last_temperature_raw(0), last_pressure_raw(0), last_humidity_raw(0), status_flags(0)
{
    std::srand(static_cast<unsigned>(std::time(nullptr)));
}

void SensorManager::init()
{
    // Initialize sensors: calibrations, offsets
    last_temperature_raw = 0;
    last_pressure_raw = 0;
    status_flags = 0x0;
    std::cout << "SensorManager initialized: sampling=" << sampling_rate_hz << "Hz ADC=" << adc_resolution_bits << "bits\n";
}

void SensorManager::on_adc_complete()
{
    // Simulate ADC reading
    int noise = (std::rand() % 50) - 25;
    // scaled representation: temperature stored with 6 fractional bits for ADC resolution of 14
    last_temperature_raw = static_cast<int16_t>((25 << 6) + noise); // scaled representation
    last_pressure_raw = static_cast<uint16_t>((1013 + (std::rand() % 10)));
    last_humidity_raw = static_cast<uint16_t>(50 + (std::rand() % 10));
    last_fuel_raw = static_cast<uint16_t>(int(50 + (std::rand() % 30)));
    status_flags = 0; // all good
}

void SensorManager::inject_fault_temperature(int16_t val)
{
    last_temperature_raw = val;
    status_flags |= 0x01; // mark temp fault
}

void SensorManager::inject_fault_pressure(uint16_t val)
{
    last_pressure_raw = val;
    status_flags |= 0x02; // mark pressure fault
}

std::vector<uint8_t> SensorManager::pack_latest()
{
    // Emit version 3 packets by default (HSI v1.2)
    std::vector<uint8_t> pkt(12, 0);
    pkt[0] = 3; // version v1.2 (v3)
    pkt[1] = 0x01; // sensor id
    pkt[2] = static_cast<uint8_t>((last_temperature_raw >> 8) & 0xFF);
    pkt[3] = static_cast<uint8_t>(last_temperature_raw & 0xFF);
    pkt[4] = static_cast<uint8_t>((last_pressure_raw >> 8) & 0xFF);
    pkt[5] = static_cast<uint8_t>(last_pressure_raw & 0xFF);
    pkt[6] = static_cast<uint8_t>((last_humidity_raw >> 8) & 0xFF);
    pkt[7] = static_cast<uint8_t>(last_humidity_raw & 0xFF);
    pkt[8] = static_cast<uint8_t>((last_fuel_raw >> 8) & 0xFF);
    pkt[9] = static_cast<uint8_t>(last_fuel_raw & 0xFF);

    // occasionally mark packet as encrypted
    bool encrypt = (std::rand() % 20) == 0; // ~5% encrypted
    if (encrypt) pkt[10] = status_flags | 0x80;
    else pkt[10] = status_flags;

    // If encrypted, XOR payload bytes with key before checksum
    const uint8_t KEY = 0x5A;
    std::vector<uint8_t> work = pkt;
    if (encrypt) {
        // encrypt bytes 0..9 (leave status_flags index 10 unencrypted)
        for (size_t i = 0; i < work.size() - 2; ++i) work[i] ^= KEY; // up to index 9
    }
    // Use CRC-8 for checksum (v2.1 onward)
    uint8_t c = crc8(work.data(), 11);
    pkt[11] = c;
    if (encrypt) {
        // store encrypted payload in packet bytes 0..10
        for (size_t i = 0; i < 11; ++i) pkt[i] = work[i];
    }
    return pkt;
}

void SensorManager::set_sampling_rate_hz(int hz)
{
    sampling_rate_hz = hz;
}
