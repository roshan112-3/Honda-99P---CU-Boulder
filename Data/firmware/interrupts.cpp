#include "interrupts.h"
#include <iostream>

void InterruptController::init()
{
    std::cout << "Interrupt controller initialized\n";
}

void InterruptController::register_handler(IRQLine line, Handler h, int priority)
{
    std::lock_guard<std::mutex> g(m);
    // for simulation we ignore priority ordering in storage but log it
    handlers[line] = h;
    std::cout << "Registered IRQ " << line << " with priority " << priority << "\n";
}

void InterruptController::raise(IRQLine line)
{
    Handler h;
    {
        std::lock_guard<std::mutex> g(m);
        if (handlers.count(line)) h = handlers[line];
    }
    if (h) {
        // In a real system, priority would determine preemption. Here we call directly.
        h();
    }
}
