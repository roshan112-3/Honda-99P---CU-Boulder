#include "sensors.h"
#include <cstdlib>
#include <ctime>
#include <iostream>

SensorManager::SensorManager()
    : sampling_rate_hz(100), adc_resolution_bits(14), last_temperature_raw(0), last_pressure_raw(0), last_humidity_raw(0), status_flags(0)
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
    status_flags = 0; // all good
}

std::vector<uint8_t> SensorManager::pack_latest()
{
    // Emit version 2 packets by default (HSI v1.1)
    std::vector<uint8_t> pkt(10, 0);
    pkt[0] = 2; // version v1.1
    pkt[1] = 0x01; // sensor id
    pkt[2] = static_cast<uint8_t>((last_temperature_raw >> 8) & 0xFF);
    pkt[3] = static_cast<uint8_t>(last_temperature_raw & 0xFF);
    pkt[4] = static_cast<uint8_t>((last_pressure_raw >> 8) & 0xFF);
    pkt[5] = static_cast<uint8_t>(last_pressure_raw & 0xFF);
    pkt[6] = static_cast<uint8_t>((last_humidity_raw >> 8) & 0xFF);
    pkt[7] = static_cast<uint8_t>(last_humidity_raw & 0xFF);
    // occasionally mark packet as encrypted
    bool encrypt = (std::rand() % 20) == 0; // ~5% encrypted
    if (encrypt) pkt[8] = status_flags | 0x80;
    else pkt[8] = status_flags;

    // If encrypted, XOR payload bytes with key before checksum
    const uint8_t KEY = 0x5A;
    std::vector<uint8_t> work = pkt;
    if (encrypt) {
        // encrypt bytes 0..7 (leave status_flags index 8 unencrypted)
        for (size_t i = 0; i < work.size() - 2; ++i) work[i] ^= KEY; // up to index 7
    }
    uint8_t sum = 0;
    for (int i = 0; i < 9; ++i) sum += work[i];
    pkt[9] = sum & 0xFF;
    if (encrypt) {
        // store encrypted payload in packet bytes 0..8
        for (size_t i = 0; i < 9; ++i) pkt[i] = work[i];
    }
    return pkt;
}

void SensorManager::set_sampling_rate_hz(int hz)
{
    sampling_rate_hz = hz;
}
