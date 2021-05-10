from enum import Enum
from libcanbadger.frame import Frame
from libcanbadger.log import Log, FrameEvent, LogEventType


# keeps track of the connection state
class InterfaceConnectionStatus(Enum):
    Unconnected = 0
    Connected = 1
    Shutdown = 2


class Interface(object):
    def __init__(self):
        self.connection_status = InterfaceConnectionStatus.Unconnected

    def connect(self, timeout: float = 10) -> bool:
        """
        needs to bring up the interface
        """
        return False

    def send_frame(self, frame, blocking=True) -> bool:
        """
        provide your own implementation for this
        :return: True on success, False otherwise
        """
        return False

    def receive_frame(self, timeout=None) -> Frame:
        """
        provide your own implementation for this
        :return: a single frame
        """
        return Frame()

    def start(self) -> None:
        """
        start receiving/sending traffic on this interface
        :return:
        """
        pass

    def stop(self) -> None:
        """
        stop receiving/sending traffic on this interfacee
        :return:
        """
        pass

    def get_connection_status(self):
        pass


class LoggedInterface(Interface):
    """
    An interface that supports logging to one or multiple Logs
    """
    def __init__(self, underlying=Interface):
        self.underlying = underlying
        self.logs = []
        # maps a log to a status
        # status = True means that the log is receiving events, False means it's disabled
        self.log_to_status_map = {}
        super(LoggedInterface, self).__init__()

    def start_log(self, name) -> Log:
        """
        start a new log and immediately start logging
        :param name: the name for this log
        :return: a new log
        """
        l = Log(name=name)
        self.logs.append(l)
        self.log_to_status_map[l] = True
        return l

    def add_log(self, log: Log) -> None:
        self.logs.append(log)

    def enable_log(self, log: Log) -> None:
        self.log_to_status_map[log] = True

    def disable_log(self, log: Log) -> None:
        self.log_to_status_map[log] = True

    def disable_all(self) -> None:
        for l in self.logs:
            self.log_to_status_map[l] = False

    def stop_log(self, log: Log = None, log_name: str = None) -> Log:
        if log:
            del self.log_to_status_map[log]
            del self.logs[self.logs.index(log)]
            return log
        if log_name:
            for l in self.logs:
                if l.name == log_name:
                    del self.log_to_status_map[l]
                    del self.logs[self.logs.index(l)]
                    return l
        raise Exception("Invalid Arguments passed to stop_log()")

    def get_log_by_name(self, name):
        for l in self.logs:
            if name == l.name:
                return l
        return None

    def receive_frame(self, timeout=None) -> Frame:
        rx_frame = self.underlying.receive_frame(timeout=timeout)
        if rx_frame.arb_id and rx_frame.payload:
            le = FrameEvent(frame=rx_frame, type=LogEventType.LOG_EVENT_RX_FRAME)
            for l in self.logs:
                if self.log_to_status_map[l]:
                    l.log(le)
        return rx_frame
    
    def send_frame(self, frame, blocking=True) -> bool:
        le = FrameEvent(frame=frame, type=LogEventType.LOG_EVENT_TX_FRAME)
        for l in self.logs:
            if self.log_to_status_map[l]:
                l.log(le)
        return self.underlying.send_frame(frame, blocking=blocking)

    def connect(self, timeout: float = 10) -> bool:
        return self.underlying.connect(timeout=timeout)

    def start(self) -> None:
        return self.underlying.start()

    def get_connection_status(self):
        return self.underlying.get_connection_status()