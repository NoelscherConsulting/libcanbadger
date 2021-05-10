#####################################################################################
# CanBadger Connection Process                                                      #
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

from multiprocessing import Process, Queue
import threading
from socket import *
import struct
import select
import random
import time
from libcanbadger.ethernet_message import EthernetMessage, EthernetMessageType, ActionType, header_unpack
from libcanbadger.interface import InterfaceConnectionStatus

def discover_canbadgers(wait_time=5) -> list:
    """
    helper function for discovering canbadgers on the network
    :param wait_time: how much time should we be looking for canbadgers
    :return: a list of dictionaries: [{'id': 'canbadger id', 'ip': '...'}, ...] or an empty list if none were found
    """
    discovered_cbs = []
    sock = socket(AF_INET, SOCK_DGRAM)  # UDP
    sock.bind(('0.0.0.0', 13370))

    start_time = time.time()
    time_spent = time.time()
    sock.settimeout(1)
    while time_spent < (start_time + wait_time):
        time_spent = time.time()
        try:
            data, addr = sock.recvfrom(256)
            data_split = data.split(b'|')
            id = data_split[1]
            node = {'id': id, 'ip': addr[0]}
            if node not in discovered_cbs:
                discovered_cbs.append(node)
        except timeout:
            continue
    sock.close()
    return discovered_cbs



# This class will establish a connection with the CANBadger
# Received messages will be put in the received_queue
# This process can be controlled by putting EthernetMessages into the command_queue
class CANBadgerConnectionProcess(Process):
    def __init__(self, canbadger_ip: str, canbadger_port: int, command_queue: Queue = Queue(),
                 received_queue: Queue = Queue(), signal_queue: Queue = Queue(), ack_queue: Queue = Queue()):
        super().__init__()

        # queues for in and output
        self.command_queue = command_queue
        self.received_queue = received_queue
        self.signal_queue = signal_queue
        self.ack_queue = ack_queue

        # udp socket for request, tcp socket for connection
        self.setup_socket = None
        self.tcp_server = socket(AF_INET, SOCK_STREAM)
        self.tcp_server.setblocking(False)
        self.port = random.randint(10000, 13369)
        self.connection = None

        # CANBadger connection socket address
        self.canbadger_ip = canbadger_ip
        self.canbadger_port = canbadger_port

        # status representation
        self.status = InterfaceConnectionStatus.Unconnected

        # input buffer
        self.receive_buffer = b''

    def set_status(self, status: InterfaceConnectionStatus):
        self.status = status
        self.signal_queue.put(status)

    def connection_setup(self) -> None:
        # prepare tcp connection on this end
        self.tcp_server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.tcp_server.bind(('', self.port))
        self.tcp_server.listen(1)

    def send_connection_command(self) -> bool:
        if self.canbadger_ip is None or self.canbadger_port is None:
            return False

        # send connection request via UDP to canbadger
        self.setup_socket = socket(AF_INET, SOCK_DGRAM)
        connection_command = EthernetMessage(EthernetMessageType.CONNECT, ActionType.NO_TYPE, 4,
                                             struct.pack('<I', self.port))
        self.setup_socket.sendto(connection_command.serialize(), (self.canbadger_ip, self.canbadger_port))
        self.setup_socket.close()
        return True

    def run(self):
        abort = threading.Event()
        socket_lock = threading.Lock()

        try:
            self.connection_setup()
            self.send_connection_command()

            # wait for CB to connect back to us
            # set socket back to blocking again, only for this step
            # this is to ensure compatibility between linux/windows etc.
            self.tcp_server.setblocking(True)
            conn, addr = self.tcp_server.accept()
            self.connection = conn
            self.set_status(InterfaceConnectionStatus.Connected)
            self.tcp_server.setblocking(False)


            def read_from_socket(sock, lock, buffer, out_q, ack_q, abort_event):
                while not abort_event.is_set():
                    readable, _, err = select.select([sock], [], [sock], 1)

                    # signal abort on errors
                    if err:
                        abort_event.set()
                        break

                    # check for network input
                    for r in readable:
                        with lock:
                            try:
                                received = r.recv(4096)
                            except ConnectionResetError:
                                abort_event.set()
                                break
                        if received is None:
                            # connection closed from other side
                            abort_event.set()
                            break
                        buffer += received

                        # extract and forward received messages
                        if len(buffer) >= 6:
                            # extract single Ethernet message from the buffer
                            _, _, msg_data_len = header_unpack(buffer[:6])
                            msg_len = msg_data_len + 6
                            raw_msg = buffer[:msg_len]
                            buffer = buffer[msg_len:]

                            # put message object in the data or ack queue
                            eth_msg = EthernetMessage.unserialize(raw_msg, unpack_data=True)
                            if eth_msg.msg_type == EthernetMessageType.ACK or eth_msg.msg_type == EthernetMessageType.NACK:
                                ack_q.put(eth_msg)
                            else:
                                out_q.put(eth_msg)

            # reader_thread to handle incoming data from socket
            reader_thread = threading.Thread(target=read_from_socket, args=(self.connection, socket_lock,
                                                                            self.receive_buffer, self.received_queue,
                                                                            self.ack_queue, abort))
            reader_thread.start()

            # react to commands from the command_queue
            while not abort.is_set():
                command = self.command_queue.get()
                if command.msg_type == EthernetMessageType.CONNECT:
                    # connect messages are invalid over an established tcp connection
                    continue
                else:
                    # forward to CANBadger
                    with socket_lock:
                        self.connection.send(command.serialize())
                if command.msg_type == EthernetMessageType.ACTION and command.action_type == ActionType.RESET:
                    abort.set()

            reader_thread.join()

            self.set_status(InterfaceConnectionStatus.Shutdown)

            self.connection.close()
            self.tcp_server.close()
            print('Connection done!')
        except KeyboardInterrupt:
            print("Shutting down ConnectionProcess..")
            abort.set()
            if self.connection:
                self.connection.close()
            if self.tcp_server:
                self.tcp_server.close()


    def send_ethernet_message(self, eth_msg: EthernetMessage):
        self.command_queue.put(eth_msg)
