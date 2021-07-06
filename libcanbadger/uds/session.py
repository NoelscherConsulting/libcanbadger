#####################################################################################
# UDS Session Object                                                                #
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

from libcanbadger.canbadger import CANBadger
from enum import Enum
from libcanbadger.ethernet_message import EthernetMessage, EthernetMessageType, ActionType
from libcanbadger.interface import InterfaceConnectionStatus
from libcanbadger.iso_tp.iso_tp_handler import IsoTpHandler
from libcanbadger.iso_tp.iso_tp_message import  IsoTpRxMessageStates
import struct
import threading
import time


class DiagnosticSession(Enum):
    NoSession = 0
    DefaultSession = 1,
    ProgrammingSession = 2,
    ExtendedSession = 3,
    SafetySession = 4


class SessionStatus(Enum):
    Setup = 0,
    Declined = 1,
    Idle = 2,
    Failed = 3


# send a tester present message to keep up the connection
def tester_present(session, stop_event, mute_event):
    while not stop_event.is_set():
        data = b'\x3e\x80'
        if not mute_event.is_set():
            session.isotp_handler.send_data(session.tester_id, data)
        time.sleep(0.5)


class Session:
    def __init__(self, interface=None, tester_id: int = None, ecu_id: int = None,
                 use_padding: bool = True, padding: int = 0xAA, use_extended_ids=False):
        # Session expects a valid and connected interface
        if interface is None:
            raise Exception("UDS Session needs a valid interface.")
        self.interface = interface
        if self.interface.get_connection_status() != InterfaceConnectionStatus.Connected:
            raise Exception("UDS Session expects an already connected interface.")

        if tester_id is None:
            raise Exception("UDS Session needs a valid tester id.")
        self.tester_id = tester_id
        if ecu_id is None:
            print("Warning: No ecu_id supplied - Will accept UDS Session from ANY ECU!")
        self.ecu_id = ecu_id
        self.use_padding = use_padding
        self.padding = padding
        self.use_extended_ids = use_extended_ids

        # create IsoTpHandler with given interface
        self.isotp_handler = IsoTpHandler(interface=self.interface, sender_id=self.tester_id, padding_byte=self.padding if self.use_padding else None)

        self.diagnostic_level = DiagnosticSession.NoSession
        self.status = SessionStatus.Setup

        self.tp_thread = None
        self.halt_tp = threading.Event()
        self.mute_tp = threading.Event()

    def __enter__(self):
        return self

    def __exit__(self, interface=None, tester_id: int = None, ecu_id: int = None, use_padding: bool = True, padding: int = 0xAA):
        self.stop_tp()
        pass

    # sends uds request and optionally returns response
    def request(self, data, wait_for_response=True, timeout=0.2):
        # disable tester present while request is active
        self.set_mute_tp(True)

        # let the IsoTpHandler and IsoTpMessage classes handle isotp and padding
        self.isotp_handler.send_data(self.tester_id, data)

        response = None
        if wait_for_response:
            if self.ecu_id is None:
                # accept response from ANY ecu
                response = self.isotp_handler.receive_message(timeout=timeout)
            else:
                response = self.isotp_handler.receive_message(arb_id=self.ecu_id, timeout=timeout)

        # reenable tp
        if self.status == SessionStatus.Idle:
            self.set_mute_tp(False)

        if wait_for_response:
            return response

    def start(self, diagnostic_level=1, timeout=1):
        data = b'\x10' + bytes([diagnostic_level])
        response = self.request(data, timeout=timeout)
        if response is None or response == b'':
            self.status = SessionStatus.Failed
            print("failed to establish session")
            return
        response_byte = response[0]
        if response_byte == 0x50:
            self.status = SessionStatus.Idle
            # start sending TesterPresent periodically
            self.start_tp()
        elif response_byte == 0x7f:
            self.status = SessionStatus.Declined
        else:
            print("unpredicted response")
            print(f"byte is {response[0]}...")

    def request_upload(self, memory_address, memory_size,  data_format_id = 0x00):
        request = b'\x35' + bytes([data_format_id])

        addr_bytes = self.calc_byte_size(memory_address)
        size_bytes = self.calc_byte_size(memory_size)
        add_len_byte = (size_bytes << 4) & 0xF0 + (addr_bytes & 0x0F)

        request += add_len_byte.to_bytes(1, byteorder='big')
        request += memory_address.to_bytes(length=addr_bytes, byteorder='big', signed=False)
        request += memory_size.to_bytes(length=size_bytes, byteorder='big', signed=False)

        # send request and interpret answer
        response = self.request(request)
        if response is None or response == b'':
            return False, b''
        else:
            return response[0] == 0x75, response[1:]

    def request_download(self, memory_address, memory_size, data_format_id = 0x00):
        request = b'\x34' + bytes([data_format_id])

        addr_bytes = self.calc_byte_size(memory_address)
        size_bytes = self.calc_byte_size(memory_size)
        add_len_byte = (size_bytes << 4) & 0xF0 + (addr_bytes & 0x0F)

        request += add_len_byte
        request += memory_address.to_bytes(length=addr_bytes, byteorder='big', signed=False)
        request += memory_size.to_bytes(length=size_bytes, byteorder='big', signed=False)

        # send request and interpret answer
        response = self.request(request)
        if response is None or response == b'':
            return False, b''
        else:
            return response[0] == 0x74, response[1:]

    def transfer_data(self, block_number, length):
        if length > 4096:
            raise Exception("Transfer size not supported")

        request  = b'\x36' + block_number.to_bytes(1, byteorder='big')
        response = self.request(request)
        if response is None or response == b'':
            return False, b''
        else:
            return response[0] == 0x76, response[1:]

    def request_vin(self):
        success, vin = self.request_data_by_id(0xf187)
        if success:
            print(f"got vin response {vin}")
        else:
            print("error receiving vin")

    def request_data_by_id(self, data_id: int):
        request = b'\x22' + data_id.to_bytes(length=2, byteorder='big', signed=False)
        response = self.request(request)
        if response is None or response == b'':
            success = False
            data = b''
        else:
            return_code = response[0]
            success = return_code == 0x62
            data = response[1:]
        return success, data

    def security_access(self, level: int, on_seed_callback: callable) -> tuple:
        """
        perform 0x27 security access
        :param level: which level to request
        :param on_seed_callback: a function to call when a seed is requested. needs to accept a bytes object as first argument, containing the seed
        :return: a tuple (success, response) containing a boolean that is true when our request was successful and the full response
        """
        request = b'\x27' + level.to_bytes(1, byteorder='big')
        response = self.request(request)
        if response is None or response == b'':
            return False, b''
        # did we receive the seed?
        if response[0] == 0x67:
            key = on_seed_callback(response[1:])
            request = b'\x27' + (level + 1).to_bytes(1, byteorder='big') + key
            response = self.request(request)
            if response is None or response == b'':
                return False, b''
            if response[0] == 0x67:
                return True, response[1:]
            else:
                return False, response[1:]
        else:
            # failed before getting the seed
            return False, response[1:]


    def start_tp(self):
        # if there is still a thread running, stop it and start a new one
        if self.tp_thread is not None:
            self.halt_tp.set()
            self.tp_thread.join()
        self.halt_tp.clear()
        self.mute_tp.clear()
        self.tp_thread = threading.Thread(target=tester_present, args=(self, self.halt_tp, self.mute_tp))
        self.tp_thread.start()

    def stop_tp(self):
        if self.tp_thread is not None:
            self.halt_tp.set()
            # self.tp_thread.join() don't wait!
        self.tp_thread = None

    def set_mute_tp(self, state: bool):
        if state:
            self.mute_tp.set()
        else:
            self.mute_tp.clear()

    def calc_byte_size(self, value):
        # TODO improve this code to include a minimum length and maybe use a formula instead of ifelse
        if value <= 0xFF:
            return 1
        elif value <= 0xFFFF:
            return 2
        elif value <= 0xFFFFFF:
            return 3
        elif value <= 0xFFFFFFFF:
            return 4
        elif value <= 0xFFFFFFFFFF:
            return 5
        elif value <= 0xFFFFFFFFFFFF:
            return 6
        elif value <= 0xFFFFFFFFFFFFFF:
            return 7
        else:
            return 8


