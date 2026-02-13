// Firmware main control loop and handlers
// Simulates sensor sampling, CAN transmission and handling interrupts

#include <iostream>
#include <thread>
#include <chrono>
#include <vector>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include "sensors.h"
#include "canbus.h"
#include "interrupts.h"

using namespace std::chrono_literals;

static std::atomic<bool> running{true};

void telemetry_thread(SensorManager &mgr, CANBus &can)
{
    // Send sensor telemetry periodically
    while (running.load()) {
        std::vector<uint8_t> pkt = mgr.pack_latest();
        can.send(pkt);
        std::this_thread::sleep_for(std::chrono::milliseconds(10)); // 100Hz
    }
}

// helper: pretty-print a packet as hex
static void print_hex(const std::vector<uint8_t> &pkt)
{
    for (auto b : pkt) printf("%02X ", b);
    printf("\n");
}

// simulate receiving a configuration CAN frame that changes behavior
void handle_config_frame(const std::vector<uint8_t> &frame, SensorManager &mgr, CANBus &can)
{
    if (frame.empty()) return;
    uint8_t cmd = frame[0];
    switch (cmd) {
        case 0x10: {
            // set sampling rate
            if (frame.size() >= 3) {
                int hz = (frame[1] << 8) | frame[2];
                mgr.set_sampling_rate_hz(hz);
                std::cout << "Config: set sampling rate=" << hz << "\n";
            }
            break;
        }
        case 0x20: {
            // request immediate telemetry
            auto pkt = mgr.pack_latest();
            can.send(pkt);
            break;
        }
        default:
            std::cout << "Unknown config cmd=" << std::hex << (int)cmd << std::dec << "\n";
    }
}

// simulate system self-test that runs a variety of checks
bool run_self_test(SensorManager &mgr, CANBus &can)
{
    std::cout << "Running self-test...\n";
    // exercise subsystems
    mgr.on_adc_complete();
    auto pkt = mgr.pack_latest();
    can.send(pkt);
    // basic validation of packet structure
    if (pkt.size() < 8) {
        std::cout << "Self-test failed: packet too small\n";
        return false;
    }
    // check checksum
    uint8_t sum = 0;
    for (size_t i = 0; i + 1 < pkt.size(); ++i) sum += pkt[i];
    if (pkt.back() != (sum & 0xFF)) {
        std::cout << "Self-test failed: bad checksum\n";
        return false;
    }
    std::cout << "Self-test ok\n";
    return true;
}

int main(int argc, char **argv)
{
    std::cout << "Firmware starting...\n";

    // Initialize components
    SensorManager sensor_mgr;
    CANBus can;
    InterruptController irq;

    sensor_mgr.init();
    can.init(500000);
    // HSI updated: new CAN ID 0x200
    can.set_tx_id(0x200);
    irq.init();

    // Register hardware interrupt callbacks
    irq.register_handler(IRQ_ADC, [&sensor_mgr]() {
        sensor_mgr.on_adc_complete();
    }, 2);

    irq.register_handler(IRQ_CAN_RX, [&can]() {
        auto frame = can.receive();
        if (!frame.empty()) {
            // simplistic dispatch
            uint16_t id = can.extract_id(frame);
            std::cout << "CAN RX ID=" << std::hex << id << std::dec << " size=" << frame.size() << "\n";
        }
    }, 3);

    // Start telemetry thread
    std::thread t(telemetry_thread, std::ref(sensor_mgr), std::ref(can));

    // Additional maintenance thread to perform diagnostics and adapt to HSI changes
    std::atomic<bool> diag_running{true};
    std::thread diag([&](){
        int counter = 0;
        while (running.load()) {
            // periodic diagnostics log
            if (counter % 100 == 0) {
                std::cout << "[DIAG] uptime ticks=" << counter << "\n";
            }
            // simulate adjusting sampling rate based on simple rule
            if (counter == 200) {
                sensor_mgr.set_sampling_rate_hz(50); // adapt to HSI change
                std::cout << "[DIAG] sampling rate adjusted to 50Hz\n";
            }
            std::this_thread::sleep_for(5ms);
            ++counter;
        }
        diag_running.store(false);
    });

    // Main loop: poll for events and simulate ADC conversions
    for (int i = 0; i < 2000 && running.load(); ++i) {
        // Simulate ADC conversions every 10ms
        std::this_thread::sleep_for(10ms);
        irq.raise(IRQ_ADC);

        // Occasionally simulate incoming CAN frame
        if (i % 50 == 0) {
            // inject a config frame sometimes
            if (i % 200 == 0) {
                // set sampling rate to 50Hz (big-endian)
                can.inject_frame({0x10, 0x00, 0x32});
            } else {
                can.inject_frame({0x18, 0x0, 0x1, 0x2, 0x3});
            }
            irq.raise(IRQ_CAN_RX);
        }
        // simulate issuing a self-test on occasion
        if (i % 600 == 0) run_self_test(sensor_mgr, can);
    }

    running.store(false);
    t.join();
    if (diag.joinable()) diag.join();

    std::cout << "Firmware shutting down\n";
    return 0;
}
