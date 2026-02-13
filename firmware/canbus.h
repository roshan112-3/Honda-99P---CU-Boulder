#pragma once
#include <vector>
#include <cstdint>
#include <mutex>

class CANBus {
public:
    CANBus();
    void init(int baud);
    void send(const std::vector<uint8_t> &payload);
    std::vector<uint8_t> receive();
    uint16_t extract_id(const std::vector<uint8_t> &frame);
    void inject_frame(const std::vector<uint8_t> &frame);
private:
    int baud_rate;
    std::vector<uint8_t> rx_buffer;
    std::mutex rx_mutex;
};
