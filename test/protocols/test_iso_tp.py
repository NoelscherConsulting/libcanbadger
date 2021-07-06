import struct

from libcanbadger.canbadger import CANBadger
from libcanbadger.interface import InterfaceConnectionStatus
from libcanbadger.iso_tp.iso_tp_message import IsoTpMessage, IsoTpRxMessageStates
from libcanbadger.iso_tp.iso_tp_handler import IsoTpHandler
from libcanbadger.frame import Frame
from libcanbadger.custom_exceptions import IsoTpException

import pytest


class MockCanBadger(CANBadger):
    def __init__(self):
        self.frame_log = []
        self.rx_sequence = []  # put frames here to be returned by receive()
        self.tx_sequence = []

    def connect(self, timeout: float = 10) -> bool:
        self.connection_status = InterfaceConnectionStatus.Connected
        return True

    def reset(self):
        self.connection_status = InterfaceConnectionStatus.Unconnected

    def reset_data(self):
        self.rx_sequence = []
        self.tx_sequence = []

    def send_frame(self, frame, blocking=True) -> bool:
        if self.connection_status == InterfaceConnectionStatus.Connected:
            self.tx_sequence.append(
                frame
            )
            return True
        else:
            return False

    def receive_frame(self, can_ids=None, timeout=1):
        if can_ids:
            for i in range(len(self.rx_sequence), 0, -1):
                if self.rx_sequence[i].arb_id in can_ids:
                    return self.rx_sequence.pop(i)
            return Frame()
        else:
            if self.rx_sequence:
                return self.rx_sequence.pop(0)
            else:
                return Frame()

    def wait_for_ack(self, timeout=None):
        return 0

    def get_connection_status(self):
        return self.connection_status


def test_iso_tp_message():
    # it should format single frame messages
    msg = IsoTpMessage(0x123, b'\x00\x01\x02')
    assert(msg.arb_id == 0x123)
    assert(msg.payload == b'\x00\x01\x02')
    frames = msg.format()
    assert(len(frames) == 1)
    assert(frames[0].payload == b'\x03\x00\x01\x02')

    # it should format multi-frame messages
    msg = IsoTpMessage(0x1eadf, bytearray([i for i in range(0, 32)]))
    frames = msg.format()
    assert(len(frames) == 5)
    assert(frames[0].payload[0] == 0x10)
    assert(frames[1].payload[0] == 0x21)
    assert(frames[2].payload[0] == 0x22)
    assert(frames[-1].payload[0] == 0x24)
    assert(frames[-1].payload_length() == 6)

    with pytest.raises(IsoTpException):
        msg = IsoTpMessage(0x123, bytes(5000))
        frames = msg.format()

    # it should read single frame messages
    msg = IsoTpMessage()
    msg.feed(Frame(arb_id=0x123, payload=b'\x02\x01\x02'))
    # ..it should apply the first received frame's id if no arb_id was provided
    assert(msg.arb_id == 0x123)
    # .. it should provide the payload length
    assert(msg.length() == 2)
    assert(msg.rx_state == IsoTpRxMessageStates.COMPLETE)
    assert(msg.payload == b'\x01\x02')

    # it should err if frames with non-matching arb_ids are fed
    msg = IsoTpMessage(arb_id=0x321)
    msg.feed(Frame(arb_id=0x123, payload=b'\x02\x01\x02'))
    assert(msg.rx_state == IsoTpRxMessageStates.ERROR)

    # it should reset
    msg.reset()
    assert(msg.rx_state == IsoTpRxMessageStates.EXPECT_SF_OR_FF)
    assert(msg.payload == b'')
    assert(msg.rx_len == 0)

    # it should read multi-frame messages
    msg = IsoTpMessage(arb_id=0x123)
    msg.feed(Frame(arb_id=0x123, payload=b'\x10\x10\x01\x02\x03\x04\x05\x06'))
    # it should move to SEND_FC state if a flow control frame could be necessary
    assert(msg.rx_state == IsoTpRxMessageStates.SEND_FC)
    msg.rx_state = IsoTpRxMessageStates.EXPECT_CF
    assert(msg.num_received == 6)
    assert(msg.rx_next_ctr == 1)
    msg.feed(Frame(arb_id=0x123, payload=b'\x21\x00\x01\x02\x03\x04\x05\x06'))
    assert(msg.rx_state == IsoTpRxMessageStates.EXPECT_CF)
    assert(msg.rx_next_ctr == 2)
    msg.feed(Frame(arb_id=0x123, payload=b'\x22\x00\x01\x02'))
    assert(msg.rx_state == IsoTpRxMessageStates.COMPLETE)
    assert(msg.num_received == 0x10)


def test_iso_tp_handler_receive():

    cb = MockCanBadger()
    cb.connect()

    assert(cb.connection_status == InterfaceConnectionStatus.Connected)

    handler = IsoTpHandler(interface=cb, sender_id=0x111)

    # it should receive messages from a certain arb_id and from any arb_id
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x02\x01\x02'))
    pl = handler.receive_message(arb_id=0x123)
    assert(pl == b'\x01\x02')
    cb.rx_sequence.append(Frame(arb_id=0x77F, payload=b'\x03\x01\x02\x03'))
    pl = handler.receive_message()
    assert(pl == b'\x01\x02\x03')

    # it should not receive a message from a different id if id arb_id is set
    cb.rx_sequence.append(Frame(arb_id=0x77F, payload=b'\x03\x01\x02\x03'))
    pl = handler.receive_message(arb_id=0x123, timeout=0.01)
    assert(pl == b'')
    cb.rx_sequence = []

    # it should receive multi-frame messages
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x10\x16\x01\x02\x03\x04\x05\x06'))
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x21\x07\x08\x09\x0a\x0b\x0c\x0d'))
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x22\x0e\x0f\x10\x11\x12\x13\x14'))
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x23\x15\x16'))
    pl = handler.receive_message(arb_id=0x123)
    assert(len(pl) == 0x16)
    for i in range(len(pl)):
        assert(pl[i] == i+1)

    # it should handle flow control during reception, if configured for it
    fctrl_frame = cb.tx_sequence[0]
    assert(fctrl_frame.arb_id == 0x111)
    assert(fctrl_frame.payload[0] == 0x30)  # type
    assert(fctrl_frame.payload[1] == 0)  # block-size
    assert(fctrl_frame.payload[2] == 100)  # delay

    # it should ignore different traffic while receiving a multiframe message
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x10\x1b\x01\x02\x03\x04\x05\x06'))
    cb.rx_sequence.append(Frame(arb_id=0x6aa, payload=b'\x03\x01\x02\x03'))  # different origin
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x21\x07\x08\x09\x0a\x0b\x0c\x0d'))
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x02\x7f\x3e'))  # ignore errors for tester present for now
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x22\x0e\x0f\x10\x11\x12\x13\x14'))
    cb.rx_sequence.append(Frame(arb_id=0x123, payload=b'\x23\x15\x16\x17\x18\x19\x1a\x1b'))
    pl = handler.receive_message(arb_id=0x123)
    assert (len(pl) == 0x1b)
    for i in range(len(pl)):
        assert (pl[i] == i + 1)


def test_iso_tp_handler_transmit():
    cb = MockCanBadger()
    if not cb.connect():
        assert False

    handler = IsoTpHandler(interface=cb, sender_id=0x123)

    # it should send single-frame messages
    payload = b'\x01\x02\x03'
    message = IsoTpMessage(arb_id=0x123, payload=payload)
    handler.send_message(message)
    assert(
        cb.tx_sequence[0].payload == b'\x03\x01\x02\x03'
    )
    assert(
        cb.tx_sequence[0].arb_id == 0x123
    )

    # it should transmit multi-frame messages
    cb.reset_data()
    length = 32
    payload = b''.join([struct.pack('B', i) for i in range(length)])
    handler.send_data(arb_id=0x123, payload=payload)
    # -> check frame values
    assert(len(cb.tx_sequence) > 0)
    for f in cb.tx_sequence:
        assert(f.arb_id == 0x123)

    tx_frame = cb.tx_sequence[0]
    assert((tx_frame[0] & 0xF0) == 0x10)  # check first frame
    assert((tx_frame[0] & 0x0F) * 256 + tx_frame[1] == length)  # check encoded length
    assert((tx_frame[0] & 0x0F) == 0x00)  # check first frame counter = 0
    tx_frame = cb.tx_sequence[1]
    assert((tx_frame[0] & 0xF0) == 0x20)  # check consecutive frame
    assert((tx_frame[0] & 0x0F) == 0x01)  # check cf counter = 1
    tx_frame = cb.tx_sequence[2]
    assert((tx_frame[0] & 0xF0) == 0x20)  # check consecutive frame
    assert((tx_frame[0] & 0x0F) == 0x02)  # check cf counter = 2

    # receive the same transmission to check for payload integrity
    cb.rx_sequence = cb.tx_sequence
    pl = handler.receive_message()
    for i in range(length):
        assert(pl[i] == i)
    cb.reset_data()

    # it should wait for flow control when sending multi-frame messages
    """
    handler = IsoTpHandler(interface=cb, sender_id=0x123, )
    payload = [struct.pack('B', i) for i in range(0,32)]
    message = IsoTpMessage(arbid=0x123, payload=payload)
    handler.send_message(message, wait_for_flow_control=True)
    assert((tx_frame[0] & 0xF0) == 0x10) # check first frame
    assert((tx_frame[0] & 0x0F) == 0x00) # check first frame counter = 0

    # now, it has to wait for a FC response
    handler.rx_feed(Frame(payload=b'\x30\x00\x00\x00\x00\x00\x00\x00'))
    """

