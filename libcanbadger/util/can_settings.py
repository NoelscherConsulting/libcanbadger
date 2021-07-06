from __future__ import annotations
import struct
import enum
import ipaddress
from libcanbadger.custom_exceptions.exceptions import CANBadgerSettingsException


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


class CANBadgerSettings(object):
    def __init__(self):
        self.id_str = ""
        self.ip_str = ""
        self.canbadger_status = 0
        self.spi_speed = 20000000
        self.can1_speed = 500000
        self.can2_speed = 500000
        self.kline1_speed = 0
        self.kline2_speed = 0

        # setting default bits
        self.set_status_bit(CanbadgerStatusBits.CAN1_STANDARD)
        self.set_status_bit(CanbadgerStatusBits.CAN2_STANDARD)

    def __eq__(self, other):
        if not isinstance(other, CANBadgerSettings):
            return NotImplemented

        equal = self.id_str == other.id_str
        equal &= self.ip_str == other.ip_str
        equal &= self.canbadger_status == other.canbadger_status
        equal &= self.spi_speed == other.spi_speed
        equal &= self.can1_speed == other.can1_speed
        equal &= self.can2_speed == other.can2_speed
        equal &= self.kline1_speed == other.kline1_speed
        equal &= self.kline2_speed == other.kline2_speed
        return equal

    def set_status_bit(self, bit: int):
        if bit not in set(sbit for sbit in CanbadgerStatusBits):
            raise CANBadgerSettingsException(message=f"{bit} is not a valid bit for the CANBadgerStatus.")
        self.canbadger_status |= (1 << bit)

    def unset_status_bit(self, bit: int):
        if bit not in set(sbit for sbit in CanbadgerStatusBits):
            raise CANBadgerSettingsException(message=f"{bit} is not a valid bit for the CANBadgerStatus.")
        self.canbadger_status &= ~(1 << bit)

    def set_id(self, ident: str):
        if not 0 <= len(ident) < 19:
            raise CANBadgerSettingsException(message=f"{len(ident)} is not a valid length for a CANBadger ID "
                                                     f"(0-18 chars).")
        self.id_str = ident

    def set_ip(self, ip: str):
        try:
            ip_obj = ipaddress.ip_address(ip)
            if type(ip_obj) == ipaddress.IPv6Address:
                raise CANBadgerSettingsException(message=f"only IPv4 addresses are valid for the CANBadger.")
            self.ip_str = ip
        except ValueError:
            raise CANBadgerSettingsException(message=f"'{ip}' is not a valid IP address.")

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
        if 0 < len(self.id_str) < 19:
            payload += struct.pack('B', len(self.id_str))
            payload += bytes(self.id_str, 'ascii')
        else:
            payload += struct.pack('B', 0)

        if 0 < len(self.id_str) < 16:
            payload += struct.pack('B', len(self.ip_str))
            payload += bytes(self.ip_str, 'ascii')
        else:
            payload += struct.pack('B', 0)

        # write status bits
        payload += struct.pack('<%dI' % len(uint32_settings), *uint32_settings)
        return payload

    @classmethod
    def deserialize(cls, raw: bytes) -> CANBadgerSettings:
        settings = CANBadgerSettings()

        # extract id string
        id_length = raw[0]
        if id_length < 0 or id_length > 18:
            raise CANBadgerSettingsException(message=f"Invalid ID length ({id_length}) while unserializing.")
        settings.id_str = raw[1:id_length + 1].decode('ascii')

        # extract ip string
        ip_length = raw[id_length + 1]
        int_start = id_length + ip_length + 2
        settings.ip_str = raw[id_length + 2:int_start].decode('ascii')

        if len(raw[int_start:]) != 6 * 4:
            raise CANBadgerSettingsException(message=f"Invalid length of raw settings while unserializing.")

        # get speed and status values
        settings.canbadger_status, settings.spi_speed, settings.can1_speed, settings.can2_speed, settings.kline1_speed,\
            settings.kline2_speed = struct.unpack('<IIIIII', raw[int_start:])

        return settings

