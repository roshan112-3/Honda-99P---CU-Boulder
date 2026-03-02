CC = g++
CFLAGS = -std=c++17 -O2 -Wall
SRCS = main.cpp sensors.cpp interrupts.cpp canbus.cpp
OBJS = $(SRCS:.cpp=.o)

all: firmware.bin

firmware.bin: $(SRCS)
	$(CC) $(CFLAGS) -o $@ $(SRCS)

clean:
	rm -f firmware.bin $(OBJS)
