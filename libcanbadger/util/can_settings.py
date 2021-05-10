import struct
import enum

class CanbadgerStatusBits(enum.IntEnum):
    SD_ENABLED = 0
    USB_SERIAL_ENABLED = 1
    ETHERNET_ENABLED = 2
    OLED_ENABLED = 3
    KEYBOARD_ENABLED = 4
    LEDS_ENABLED = 5
    KLINE1_INT_ENABLED = 6
    KLINE2_INT_ENABLED = 7
    CAN1_INT_ENABLED = 8
    CAN2_INT_ENABLED = 9
    KLINE_BRIDE_ENABLED = 10
    CAN_BRIDGE_ENABLED = 11
    CAN1_LOGGING = 12
    CAN2_LOGGING = 13
    KLINE1_LOGGING = 14
    KLINE2_LOGGING = 15
    CAN1_STANDARD = 16
    CAN1_EXTENDED = 17
    CAN2_STANDARD = 18
    CAN2_EXTENDED = 19
    CAN1_TO_CAN2_BRIDGE = 20
    CAN2_TO_CAN1_BRIDGE = 21
    KLINE1_TO_KLINE2_BRIDGE = 22
    KLINE2_TO_KLINE1_BRIDGE = 23
    UDS_CAN1_ENABLED = 24
    UDS_CAN2_ENABLED = 25
    CAN1_USE_FULLFRAME = 26
    CAN2_USE_FULLFRAME = 27
    CAN1_MONITOR = 28
    CAN2_MONITOR = 29

class CanBadgerSettings(object):
    def __init__(self):
        self.id_str = ""
        self.ip_str = ""
        self.canbadger_status = 0
        self.spi_speed = 20000000
        self.can1_speed = 500000
        self.can2_speed = 500000
        self.kline1_speed = 0
        self.kline2_speed = 0

    def set_status_bit(self, bit: int):
        self.canbadger_status |= (1 << bit)

    def serialize(self) -> bytes:
        """
        format is:
        [id len] [id str ..] [ip len] [ip str ..] [u32 status] [u32 spi speed] ...

        status encodes enable flags for can1, can2 etc.
        :return: a bytes object, ready to be included in an EthernetMessage to the CB
        """
        uint32_settings = [
            self.canbadger_status, self.spi_speed, self.can1_speed, self.can2_speed,
            self.kline1_speed, self.kline2_speed
        ]

        payload = b''
        payload += struct.pack('B', len(self.id_str))
        if len(self.id_str) > 0 and len(self.id_str) < 16:
            payload += bytes(self.id_str, 'ascii')
        payload += struct.pack('B', len(self.ip_str))
        if len(self.ip_str) > 0 and len(self.id_str) < 16:
            payload += bytes(self.ip_str, 'ascii')
        # write status bits
        payload += struct.pack('<%dI' % len(uint32_settings), *uint32_settings)
        return payload


