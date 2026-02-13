#pragma once
#include <vector>
#include <cstdint>
#include <mutex>

class CANBus {
public:
    CANBus();
    void init(int baud);
    void set_tx_id(uint16_t id);
    void send(const std::vector<uint8_t> &payload);
    void send_with_id(uint16_t id, const std::vector<uint8_t> &payload);
    std::vector<uint8_t> receive();
    uint16_t extract_id(const std::vector<uint8_t> &frame);
    void inject_frame(const std::vector<uint8_t> &frame);
private:
    int baud_rate;
    std::vector<uint8_t> rx_buffer;
    std::mutex rx_mutex;
    uint16_t tx_id;
};
