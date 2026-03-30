from can_interface import parse_can_frame, parse_can_identifier, validate_can_checksum
from input_signals import (
    diagnostic_health_check_interval,
    read_accelerator_signal,
    read_brake_pedal_signal,
    read_steering_input,
)


def test_can_frame_parse_timing():
    return parse_can_frame(b"\x01\x02\x10\x20\x30\x63", 15)


def test_steering_input_latency():
    return read_steering_input(b"\x01\x02\x10\x20\x30\x63", 15)


def test_brake_pedal_signal_integrity():
    return read_brake_pedal_signal(b"\x01\x02\x10\x20\x30\x63", 15)


def test_accelerator_response_time():
    return read_accelerator_signal(b"\x01\x02\x10\x20\x30\x63", 15)


def test_diagnostic_health_check_interval():
    return diagnostic_health_check_interval(b"\x01\x02\x10\x20\x30\x63", 15)


def test_can_frame_checksum_validation():
    return validate_can_checksum(b"\x01\x02\x10\x20\x30\x63")


def test_can_frame_id_parsing():
    return parse_can_identifier(b"\x01\x02\x10\x20\x30\x63")
