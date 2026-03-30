#pragma once
#include <functional>
#include <map>
#include <mutex>

enum IRQLine { IRQ_ADC = 0, IRQ_CAN_RX = 1 };

class InterruptController {
public:
    using Handler = std::function<void()>;
    void init();
    // register with priority (lower means higher priority)
    void register_handler(IRQLine line, Handler h, int priority = 10);
    void raise(IRQLine line);
private:
    std::map<IRQLine, Handler> handlers;
    std::mutex m;
};
