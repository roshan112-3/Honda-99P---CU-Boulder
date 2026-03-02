#include "gps.h"
#include <cmath>
#include <ctime>
#include <sstream>
#include <iomanip>
#include <random>

GPSModule::GPSModule() : seq(0) {}

void GPSModule::init()
{
    // pretend to initialize UART and chipset
}

GPSFix GPSModule::read_fix()
{
    // Simulate a GPS fix with drifting coordinates
    std::random_device rd;
    std::mt19937 gen(rd());
    std::normal_distribution<> dlat(0.0, 0.0001);
    std::normal_distribution<> dlon(0.0, 0.0001);

    GPSFix f;
    f.lat = 37.421998 + dlat(gen);
    f.lon = -122.084000 + dlon(gen);
    f.alt = 15.0 + (std::rand() % 10);
    f.fix_type = 2;
    f.unix_ts = static_cast<uint32_t>(std::time(nullptr));
    seq++;
    return f;
}

std::string GPSModule::nmea_from_fix(const GPSFix &f)
{
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(6);
    ss << "$GPGGA," << f.unix_ts << "," << f.lat << ",N," << f.lon << ",W," << int(f.fix_type) << ",07,1.0," << f.alt << ",M,,,*00";
    return ss.str();
}
