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

int main(int argc, char **argv)
{
    std::cout << "Firmware starting...\n";

    // Initialize components
    SensorManager sensor_mgr;
    CANBus can;
    InterruptController irq;

    sensor_mgr.init();
    can.init(500000);
    irq.init();

    // Register hardware interrupt callbacks
    irq.register_handler(IRQ_ADC, [&sensor_mgr]() {
        sensor_mgr.on_adc_complete();
    });

    irq.register_handler(IRQ_CAN_RX, [&can]() {
        auto frame = can.receive();
        if (!frame.empty()) {
            // simplistic dispatch
            uint16_t id = can.extract_id(frame);
            std::cout << "CAN RX ID=" << std::hex << id << std::dec << " size=" << frame.size() << "\n";
        }
    });

    // Start telemetry thread
    std::thread t(telemetry_thread, std::ref(sensor_mgr), std::ref(can));

    // Main loop: poll for events and simulate ADC conversions
    for (int i = 0; i < 500 && running.load(); ++i) {
        // Simulate ADC conversions every 10ms
        std::this_thread::sleep_for(10ms);
        irq.raise(IRQ_ADC);

        // Occasionally simulate incoming CAN frame
        if (i % 50 == 0) {
            can.inject_frame({0x18, 0x0, 0x1, 0x2, 0x3});
            irq.raise(IRQ_CAN_RX);
        }
    }

    running.store(false);
    t.join();

    std::cout << "Firmware shutting down\n";
    return 0;
}
