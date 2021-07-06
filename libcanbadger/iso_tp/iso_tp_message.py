import enum
import struct

from libcanbadger.frame import Frame
from libcanbadger.custom_exceptions import IsoTpException


class IsoTpRxMessageStates(enum.Enum):
    """
    intermediary states for when we're parsing an IsoTp message
    """
    EXPECT_SF_OR_FF = 0,  # can go to COMPLETE, SEND_FC or ERROR
    EXPECT_CF = 1,  # can go to COMPLETE, FINISHED OR ERROR
    COMPLETE = 2,  # terminal
    ERROR = 3,  # terminal
    SEND_FC = 4,  # can go to EXPECT_CF or ERROR


class IsoTpFrameFlags(enum.IntEnum):
    SF = 0x00  # single frame
    FF = 0x10  # first frame
    CF = 0x20  # consecutive frame
    FC = 0x30  # flow control


class IsoTpBitmasks(enum.IntEnum):
    FRAME_TYPE = 0xF0
    LEN_OR_CTR = 0x0F


class IsoTpMessage:
    """
    Type for ISO-TP messages.
    """
    def __init__(self, arb_id=None, payload=None, padding_byte=None):
        """
        IsoTpMessage constructor
        :param arb_id: specifies which can arbitration ID to use
        :param payload: the raw payload, as bytes
        :param flowcontrol:
        :param padding_byte: a value to use for padding messages that don't fill up the whole frame
        """
        self.arb_id = arb_id
        self.payload = payload
        self.rx_state = IsoTpRxMessageStates.EXPECT_SF_OR_FF
        self.num_received = 0
        self.rx_len = 0
        self.rx_next_ctr = 0
        self.padding_byte = padding_byte

    def reset(self):
        """
        call this when you want to 'reuse' a message that has already been parsed
        will delete the payload and reset internal state so you can call feed() again
        :returns: nothing
        """
        self.rx_state = IsoTpRxMessageStates.EXPECT_SF_OR_FF
        self.num_received = 0
        self.rx_len = 0
        self.rx_next_ctr = 0
        self.payload = b''

    def feed(self, frame: Frame) -> bool:
        """
        feed the message a single Frame to parse incoming IsoTp messages
        :returns: bool if parsing complete
        """
        # the frame must have at least one byte length
        if len(frame.payload) < 1:
            self.rx_state = IsoTpRxMessageStates.ERROR
            return False

        # IsoTpMessage ignores flow control messages. the handler is in charge of that
        if frame.payload[0] & IsoTpBitmasks.FRAME_TYPE == IsoTpFrameFlags.FC:
            if self.rx_state != IsoTpRxMessageStates.COMPLETE:
                return False
            else:
                return True

        if self.rx_state == IsoTpRxMessageStates.EXPECT_SF_OR_FF:
            # if arb_id was set, we check if it matches
            if self.arb_id:
                if not frame.arb_id == self.arb_id:
                    # if it doesn't match, we immediately go to the error state
                    # filtering frames is not our job
                    self.rx_state = IsoTpRxMessageStates.ERROR
                    return False
            else:
                # if arb_id is not set, we set it to the first received Frame's arb_id
                self.arb_id = frame.arb_id
            if frame.payload[0] & IsoTpBitmasks.FRAME_TYPE == IsoTpFrameFlags.SF:
                content_length = frame[0] & IsoTpBitmasks.LEN_OR_CTR
                self.payload = frame.payload[1:content_length+1]
                self.num_received = len(self.payload)
                self.rx_state = IsoTpRxMessageStates.COMPLETE
                return True
            elif frame.payload[0] & IsoTpBitmasks.FRAME_TYPE == IsoTpFrameFlags.FF:
                self.rx_len = (frame.payload[0] & IsoTpBitmasks.LEN_OR_CTR) * 256 + frame.payload[1]
                self.rx_state = IsoTpRxMessageStates.SEND_FC
                self.num_received = len(frame.payload[2:])
                self.payload = frame.payload[2:]
                self.rx_next_ctr = 1
                return False
            else:
                self.rx_state = IsoTpRxMessageStates.ERROR
        if self.rx_state == IsoTpRxMessageStates.EXPECT_CF:
            if frame.payload[0] & IsoTpBitmasks.FRAME_TYPE == IsoTpFrameFlags.CF and \
                    frame.payload[0] & IsoTpBitmasks.LEN_OR_CTR == self.rx_next_ctr:
                rx_payload_len = len(frame.payload[1:])
                rx_bytes_remaining = self.rx_len - self.num_received
                rx_bytes_to_read = 7 if rx_bytes_remaining > 7 else rx_bytes_remaining  # TODO check for extended frames
                self.payload += frame.payload[1:rx_bytes_to_read+1]
                self.num_received += rx_payload_len
                self.rx_next_ctr += 1
                if self.num_received >= self.rx_len:
                    # we're done!
                    self.rx_state = IsoTpRxMessageStates.COMPLETE
                    return True
            else:
                self.rx_state = IsoTpRxMessageStates.ERROR
        if self.rx_state == IsoTpRxMessageStates.COMPLETE:
            return True
        if self.rx_state == IsoTpRxMessageStates.ERROR:
            pass

        return False

    def length(self):
        """
        :return: the payload length
        """
        return len(self.payload)

    def format(self, max_frame_len=7) -> list:
        """
        :param max_frame_len:
        :return: a list of libcanbadger Frames
        """
        frames = []
        if len(self.payload) > max_frame_len:
            # multi-frame
            # create first frame

            # encode data length
            byte_count = len(self.payload)
            if byte_count > 4095:
                raise IsoTpException(message=f"Payload Length of {byte_count} exceeds the protocols "
                                             f"maximum of 4095 bytes")
            first_short = (byte_count + 0x1000).to_bytes(2, byteorder='big', signed=False)
            frames.append(Frame(
                arb_id=self.arb_id,
                payload=first_short + self.payload[:6]
            ))
            # add the remaining CFs
            for i in range(1, int(byte_count/max_frame_len)+1):
                frames.append(Frame(
                    arb_id=self.arb_id,
                    payload=self.pad_message(struct.pack('B', (0x20 | (i % 0x0F))) +
                                             self.payload[i * max_frame_len - 1:(1 + i) * max_frame_len - 1])
                ))

            # add last frame
            return frames
        else:
            # single frame
            return [Frame(
                arb_id=self.arb_id,
                payload=self.pad_message(struct.pack('B', len(self.payload) % 0x0F) + self.payload)
            )]

    def pad_message(self, msg):
        if len(msg) < 8 and self.padding_byte is not None:
            pad_byte_cnt = 8 - len(msg)
            return msg + bytes([self.padding_byte] * pad_byte_cnt)
        else:
            return msg