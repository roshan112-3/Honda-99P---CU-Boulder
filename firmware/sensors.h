#pragma once
#include <vector>
#include <cstdint>

class SensorManager {
public:
    SensorManager();
    void init();
    void on_adc_complete();
    std::vector<uint8_t> pack_latest();
    void set_sampling_rate_hz(int hz);
private:
    int sampling_rate_hz;
    int adc_resolution_bits;
    int16_t last_temperature_raw;
    uint16_t last_pressure_raw;
    uint8_t status_flags;
};
