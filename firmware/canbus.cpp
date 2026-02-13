#include "canbus.h"
#include <iostream>

CANBus::CANBus() : baud_rate(500000) {}

void CANBus::init(int baud)
{
    baud_rate = baud;
    std::cout << "CAN bus initialized at " << baud_rate << " bps\n";
}

void CANBus::send(const std::vector<uint8_t> &payload)
{
    // Simulated: print to stdout using configured TX id
    uint16_t id = tx_id ? tx_id : 0x180;
    std::cout << "CAN TX [ID=0x" << std::hex << id << "] " << std::dec;
    for (auto b : payload) {
        printf("%02X ", b);
    }
    std::cout << "\n";
}

void CANBus::set_tx_id(uint16_t id)
{
    tx_id = id;
    std::cout << "CANBus set_tx_id to 0x" << std::hex << tx_id << std::dec << "\n";
}

std::vector<uint8_t> CANBus::receive()
{
    std::lock_guard<std::mutex> g(rx_mutex);
    if (rx_buffer.empty()) return {};
    auto ret = rx_buffer;
    rx_buffer.clear();
    return ret;
}

uint16_t CANBus::extract_id(const std::vector<uint8_t> &frame)
{
    if (frame.size() >= 2) return (static_cast<uint16_t>(frame[0]) << 8) | frame[1];
    if (frame.size() == 1) return frame[0];
    return 0;
}

void CANBus::inject_frame(const std::vector<uint8_t> &frame)
{
    std::lock_guard<std::mutex> g(rx_mutex);
    rx_buffer = frame;
}
