import enum
import time
from libcanbadger.CANBadger import CANBadger
from libcanbadger.interface import Interface, InterfaceConnectionStatus
from libcanbadger.iso_tp.iso_tp_message import IsoTpMessage, IsoTpRxMessageStates
from libcanbadger.frame import Frame


class IsoTpHandler(object):
    """
    IsoTpHandler defines a bridge between your application and IsoTpMessages
    It handles sending and receiving IsoTpMessages using a single interface
    """
    def __init__(self, interface: Interface, sender_id: int, padding_byte=None):
        self.messages = {}
        self.interface = interface
        self.sender_id = sender_id
        self.padding_byte = padding_byte

    def register_message(self, name: str, arb_id: int, payload: bytes = None) -> None:
        """
        register a message for both sending & receiving
        you should register messages when you expect to send or receive them periodically
        if you need to send a one-off message, use send_message(..)
        :return: nothing
        """
        msg = IsoTpMessage(arb_id=arb_id, payload=payload)
        self.messages[name] = msg

    def get_messages(self) -> list:
        return list(self.messages.values())

    def send_registered_message(self, name: str) -> bool:
        """
        transmit a registered message
        :return:
        """
        msg = self.messages[name]
        self.send_message(msg)

    def send_message(self, msg: IsoTpMessage) -> bool:
        """
        send a message straight away, without registering it
        """
        frames = msg.format()
        for frame in frames:
            self.interface.send_frame(frame)

    def send_data(self, arb_id: int, payload: bytes):
        """
        send some binary payload, using the user-supplied arbitration id
        does not register the resulting message
        this is essentially syntactic sugar around IsoTpMessage's constructor
        """
        msg = IsoTpMessage(arb_id=arb_id, payload=payload, padding_byte=self.padding_byte)
        self.send_message(msg)

    def send_flowcontrol(self, command=0, block_size=0, delay=100):
        pl = bytes([command + 0x30, block_size, delay])
        if self.padding_byte:
            pl += bytes([self.padding_byte] * 5)
        fc_frame = Frame(arb_id=self.sender_id, payload=pl)
        self.interface.send_frame(fc_frame)

    def receive_registered_message(self, name) -> IsoTpMessage:
        """
        blocks until a registered message with name=name is received
        :return: the received message
        """
        pass

    def receive_message(self, arb_id: int, timeout=None) -> bytes:
        """
        blocks until a message is received with arbitration id = arb_id
        no message is registered
        :return: the received message
        """
        if self.interface.get_connection_status() != InterfaceConnectionStatus.Connected:
            raise Exception("IsoTpHandler: Interface is not connected! Aborting.")

        msg = IsoTpMessage(arb_id=arb_id)
        msg.arb_id = arb_id

        # receive frames and see if we can feed them
        while msg.rx_state != IsoTpRxMessageStates.COMPLETE:
            frame = self.interface.receive_frame(timeout=timeout)
            if frame.payload is None:
                msg.rx_state = IsoTpRxMessageStates.ERROR
                print('empty frame --> timeout')
            elif msg.arb_id == frame.arb_id:
                # filter out tester present messages here TEST
                if frame.payload[1] == 0x7f and frame.payload[2] == 0x3e:
                    print('received bad TP response!!')
                else:
                    msg.feed(frame)

            if msg.rx_state == IsoTpRxMessageStates.ERROR:
                # we return an erroneous message as soon as we get the error
                break
            # send FlowControl after first frame
            if msg.rx_state == IsoTpRxMessageStates.SEND_FC:
                self.send_flowcontrol(command=0, block_size=0, delay=100)
                msg.rx_state = IsoTpRxMessageStates.EXPECT_CF
        # if all is good, we return the complete received message
        if msg.rx_state == IsoTpRxMessageStates.COMPLETE:
            return msg.payload
        else:
            return b''
