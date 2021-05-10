#####################################################################################
# CanBadger Class                                                                   #
# Copyright (c) 2021 Noelscher Consulting GmbH                                      #
#                                                                                   #
# Permission is hereby granted, free of charge, to any person obtaining a copy      #
# of this software and associated documentation files (the "Software"), to deal     #
# in the Software without restriction, including without limitation the rights      #
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell         #
# copies of the Software, and to permit persons to whom the Software is             #
# furnished to do so, subject to the following conditions:                          #
#                                                                                   #
# The above copyright notice and this permission notice shall be included in        #
# all copies or substantial portions of the Software.                               #
#                                                                                   #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR        #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,          #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE       #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER            #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,     #
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN         #
# THE SOFTWARE.                                                                     #
#####################################################################################

from libcanbadger.CANBadgerConnectionProcess import CANBadgerConnectionProcess
from libcanbadger.ethernet_message import EthernetMessage, EthernetMessageType, ActionType
from libcanbadger.interface import Interface, InterfaceConnectionStatus
from libcanbadger.frame import Frame
from libcanbadger.util.can_settings import CanBadgerSettings
from multiprocessing import Queue
from queue import Empty
import time
import platform
from os import kill
import subprocess
import struct


class CANBadger(Interface):
    """
    Providing an interface implementation to the CANBadger
    """
    def __init__(self, canbadger_ip: str, canbadger_port: int = 13371):
        super(CANBadger, self).__init__()
        self.canbadger_ip = canbadger_ip
        self.canbadger_port = canbadger_port

        self.command_queue = Queue()
        self.signal_queue = Queue()
        self.data_queue = Queue()
        self.ack_queue = Queue()
        self.queues = [self.command_queue, self.signal_queue, self.data_queue, self.ack_queue]

        self.connection_process = CANBadgerConnectionProcess(self.canbadger_ip, self.canbadger_port,
                                                             command_queue=self.command_queue,
                                                             received_queue=self.data_queue,
                                                             signal_queue=self.signal_queue,
                                                             ack_queue=self.ack_queue)

    def configure(self, settings: CanBadgerSettings):
        # send settings to canbadger
        payload = settings.serialize()
        eth_msg = EthernetMessage(EthernetMessageType.ACTION, ActionType.SETTINGS, len(payload), payload)
        # send settings to canbadger
        ret = self.send(eth_msg)
        # TODO: investigate this
        # ..for some reason, the canbadger needs ~250ms to start logging
        # -> we fix it here by waiting a bit
        time.sleep(0.3)
        return ret

    def connect(self, timeout: float = 10) -> bool:
        """
        start the connection process that will connect to the CANBadger
        :param timeout: timeout in s
        :return: bool signaling if connection was established before timeout
        """
        self.connection_process.start()
        if not self.signal_queue.empty():
            self.connection_status = self.signal_queue.get()
            if self.connection_status == InterfaceConnectionStatus.Connected:
                return True
        for i in range(10):
            time.sleep(timeout/10)
            if not self.signal_queue.empty():
                self.connection_status = self.signal_queue.get()
                if self.connection_status == InterfaceConnectionStatus.Connected:
                    return True
        return False

    def reset(self):
        """
        reset the CANBadger and the Connection
        :return: nothing
        """
        self.get_connection_status()
        if self.connection_status == InterfaceConnectionStatus.Unconnected:
            if platform.system() == "Linux":
                kill(self.connection_process.pid, -1)
            else:
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.connection_process.pid)])
        else:
            self.shutdown_connection()
            self.connection_process.join()

        self.connection_process = CANBadgerConnectionProcess(self.canbadger_ip, self.canbadger_port,
                                                             command_queue=self.command_queue,
                                                             received_queue=self.data_queue,
                                                             signal_queue=self.signal_queue,
                                                             ack_queue=self.ack_queue)
        self.connection_status = InterfaceConnectionStatus.Unconnected

        # empty the queues
        for q in self.queues:
            self.empty_queue(q)
        return 0

    def receive(self, timeout: float = None):
        """
        receive an EthernetMessage from the CANBadger
        :param timeout: timeout in s
        :return:
        """
        self.get_connection_status()
        if self.connection_status != InterfaceConnectionStatus.Connected:
            return -1

        try:
            eth_msg = self.data_queue.get_nowait()
            return eth_msg
        except Empty:
            if timeout is None:
                return -1
        try:
            eth_msg = self.data_queue.get(timeout=timeout)
            return eth_msg
        except Empty:
            pass
        return -1

    def send(self, eth_msg, wait_for_ack=False):
        """
        send an ethernet message to the CANBadger
        :param eth_msg: EthernetMessage to send
        :param wait_for_ack: do we expect the CANBadger to ACK the message
        :return: 0 or -1 if ACK failed
        """
        self.command_queue.put(eth_msg)
        if wait_for_ack:
            return self.wait_for_ack(1)
        else:
            return 0

    # send a canframe out from one of the CANBadgers CAN interfaces
    def send_canframe(self, payload, arb_id, interface=1, extended_id=False):
        # send a START_REPLAY command with the canframe to the CANBadger
        if extended_id:
            arb_id = arb_id | 0x80000000
        replay_payload = struct.pack('B', interface) + struct.pack('I', arb_id) + payload
        return self.send(EthernetMessage(EthernetMessageType.ACTION, ActionType.START_REPLAY,
                                         len(replay_payload), replay_payload), wait_for_ack=True) == 0

    # call receive_canframe when the CANBadger is logging to receive the next logged payload
    def receive_canframe(self, can_ids=None, timeout=1):
        while True:
            # receive a logged canframe, if ids is set, retry until a valid one is found
            can_id = 0x0
            logging_response = self.receive(timeout=timeout)
            if logging_response == -1:
                return None, None
            if logging_response.msg_type != EthernetMessageType.DATA:
                continue
            can_id = struct.unpack('>I', logging_response.data[5:9])[0]
            if can_ids:
                # check if the logged canframes id is in the list
                if can_id in can_ids:
                    break
                else:
                    continue
            else:
                break

        # extract the canframe from the logging response
        response = logging_response.data[14:]
        return can_id, response

    def send_frame(self, frame, blocking=True) -> bool:
        return self.send_canframe(payload=frame.payload, arb_id=frame.arb_id)

    def receive_frame(self, timeout=None) -> Frame:
        arb_id, payload = self.receive_canframe(timeout=timeout)
        if arb_id is None:
            return Frame()
        return Frame(arb_id=arb_id, payload=payload)

    def wait_for_ack(self, timeout=None):
        try:
            if timeout:
                ack = self.ack_queue.get(timeout=timeout)
            else:
                ack = self.ack_queue.get()
            if ack is None or ack.msg_type == EthernetMessageType.NACK:
                return -1
            return 0
        except Empty:
            return -1

    def get_connection_status(self):
        # update local status from signal queue
        try:
            self.connection_status = self.signal_queue.get_nowait()
        except Empty:
            return self.connection_status

    @staticmethod
    def empty_queue(q):
        try:
            q.get_nowait()
        except Empty:
            return

    def set_gpio(self, gpio_num: int = 1, state: bool = False):
        # first byte is which gpio, second byte is desired state
        gpio = b'\x01'
        if gpio_num == 2:
            gpio = b'\x02'

        gpio_set = b'\x00'
        if state:
            gpio_set = b'\x01'

        msg = EthernetMessage(EthernetMessageType.ACTION, ActionType.RELAY, 2, gpio + gpio_set)
        self.send(msg)


    # helper methods with prepared ethernet messages

    def send_ack(self):
        self.send(EthernetMessage(EthernetMessageType.ACK, ActionType.NO_TYPE, 0, b''))

    def send_nack(self):
        self.send(EthernetMessage(EthernetMessageType.NACK, ActionType.NO_TYPE, 0, b''))

    def send_stop(self):
        self.send(EthernetMessage(EthernetMessageType.ACTION, ActionType.STOP_CURRENT_ACTION, 0, b''))

    def shutdown_connection(self):
        self.send(EthernetMessage(EthernetMessageType.ACTION, ActionType.RESET, 0, b''))

    def request_settings(self):
        self.send(EthernetMessage(EthernetMessageType.ACTION, ActionType.SETTINGS, 0, b''))

    def start(self):
        self.send(EthernetMessage(EthernetMessageType.ACTION, ActionType.LOG_RAW_CAN_TRAFFIC, 0, b''), wait_for_ack=True)

    def stop(self):
        self.send(EthernetMessage(EthernetMessageType.ACTION, ActionType.STOP_CURRENT_ACTION, 0, b''))




