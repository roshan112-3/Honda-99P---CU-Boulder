#include "interrupts.h"
#include <iostream>

void InterruptController::init()
{
    std::cout << "Interrupt controller initialized\n";
}

void InterruptController::register_handler(IRQLine line, Handler h)
{
    std::lock_guard<std::mutex> g(m);
    handlers[line] = h;
}

void InterruptController::raise(IRQLine line)
{
    Handler h;
    {
        std::lock_guard<std::mutex> g(m);
        if (handlers.count(line)) h = handlers[line];
    }
    if (h) h();
}
