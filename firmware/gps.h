#pragma once
#include <cstdint>
#include <string>

struct GPSFix {
    double lat;
    double lon;
    double alt;
    uint8_t fix_type; // 0 = none, 1 = 2D, 2 = 3D
    uint32_t unix_ts;
};

class GPSModule {
public:
    GPSModule();
    void init();
    GPSFix read_fix();
    std::string nmea_from_fix(const GPSFix &f);
private:
    uint32_t seq;
};
