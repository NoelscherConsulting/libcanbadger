from libcanbadger.util.can_settings import CANBadgerSettings, CanbadgerStatusBits, CANBadgerSettingsException
import pytest

def test_canbadger_settings():
    # set name to testCB, enable logging on CAN1, CAN1 speed = CAN2 speed = 500000, ip = 10.0.0.69
    # it should match the default settings
    reference = b'\x06testCB\t10.0.0.69\x01\x00\x05\x00\x00-1\x01 \xa1\x07\x00 \xa1\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    settings = CANBadgerSettings()
    settings.ip_str = "10.0.0.69"
    settings.id_str = "testCB"
    settings.set_status_bit(CanbadgerStatusBits.CAN1_STANDARD)
    settings.set_status_bit(CanbadgerStatusBits.CAN2_STANDARD)
    settings.set_status_bit(CanbadgerStatusBits.SD_ENABLED)
    settings.can1_speed = 500000
    settings.can2_speed = 500000
    settings.spi_speed = 20000000
    assert(settings.serialize() == reference)

    # testing the deserialization
    reference_settings = CANBadgerSettings.deserialize(reference)
    assert(reference_settings == settings)

    # it should omit ip, id if not changed
    reference = b'\x00\x00\x01\x00\x05\x00\x00-1\x01 \xa1\x07\x00 \xa1\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    settings.ip_str = ""
    settings.id_str = ""
    assert(settings.serialize() == reference)

    # test for invalid inputs
    with pytest.raises(CANBadgerSettingsException):
        settings.set_id("thisisaverylongcanbadgerid")

    with pytest.raises(CANBadgerSettingsException):
        settings.set_ip("10.12")

    with pytest.raises(CANBadgerSettingsException):
        settings.set_status_bit(30)