from libcanbadger.frame import Frame
import json
import enum
from binascii import hexlify, unhexlify

class LogEventType(enum.IntEnum):
    LOG_EVENT_RX_FRAME = 0
    LOG_EVENT_TX_FRAME = 1
    LOG_EVENT_NAMED_EVENT = 2

class LogEvent(object):
    def __init__(self, type: int):
        self.type = type

    def serialize(self) -> str:
        pass

    @staticmethod
    def from_dict(json_obj: dict) -> object:
        pass

    def pretty_print(self) -> None:
        print(f"{self.type}: {self}")

class FrameEvent(LogEvent):
    """
    used for logging received/transmitted CanFrames
    """
    def __init__(self, frame: Frame, type: LogEventType):
        if type not in [LogEventType.LOG_EVENT_RX_FRAME, LogEventType.LOG_EVENT_TX_FRAME]:
            raise Exception("Invalid type provided to FrameEvent!")
        super(FrameEvent, self).__init__(type)
        self.frame = frame

    def serialize(self) -> str:
        return json.dumps({
            'type': self.type,
            'arb_id': hex(self.frame.arb_id),
            'payload': ' '.join([hex(i) for i in self.frame.payload])
        })

    @staticmethod
    def from_dict(json_obj: dict) -> object:
        if json_obj['type'] not in [LogEventType.LOG_EVENT_RX_FRAME, LogEventType.LOG_EVENT_TX_FRAME]:
            raise Exception("Tried parsing a FrameEvent with invalid type!")

        return FrameEvent(
            frame=Frame(arb_id=int(json_obj['arb_id'], 16), payload=bytes.fromhex(json_obj['payload']))
        )

    def pretty_print(self) -> None:
        print(f"[{'RX' if self.type == LogEventType.LOG_EVENT_RX_FRAME else 'TX'}] {hex(self.frame.arb_id)} {' '.join([hex(i) for i in self.frame.payload])}")

class NamedEvent(LogEvent):
    def __init__(self, name):
        super(NamedEvent, self).__init__(type=LogEventType.LOG_EVENT_NAMED_EVENT)
        self.name = name

    def serialize(self) -> str:
        return json.dumps({
            'name': self.name
        })

    @staticmethod
    def from_dict(json_obj: dict) -> object:
        if json_obj['type'] != LogEventType.LOG_EVENT_NAMED_EVENT:
            raise Exception("Tried parsing a NamedEvent with invalid type!")
        return NamedEvent(
            name = json_obj['name']
        )

    def pretty_print(self) -> None:
        print(f"-> {self.name}")

class JsonLogEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, LogEvent):
            return o.serialize()
        else:
            return json.JSONEncoder.default(self, o)

class Log(object):
    def __init__(self, name=None):
        self.name = name
        self.events = []
        self.current_iter_index = 0

    def __len__(self):
        return len(self.events)

    def __iter__(self):
        self.current_iter_index = 0
        return self

    def __next__(self):
        if self.current_iter_index < len(self.events):
            ev =  self.events[self.current_iter_index]
            self.current_iter_index += 1
            return ev
        else:
            raise StopIteration

    def log(self, event: LogEvent) -> None:
        self.events.append(event)

    def pretty_print(self) -> None:
        for ev in self.events:
            ev.pretty_print()

    def to_json(self) -> str:
        return json.dumps(self.events, cls=JsonLogEncoder)

    def save_to_file(self, filename: str) -> None:
        with open(filename, 'w') as f:
            json.dump(self.events, f, cls=JsonLogEncoder)

    @staticmethod
    def from_json(json_str: str) -> object:
        log = Log()

        # add object hook
        def parse_log_event(dct):
            if 'type' in dct:
                if dct['type'] in [LogEventType.LOG_EVENT_RX_FRAME, LogEventType.LOG_EVENT_TX_FRAME]:
                    return FrameEvent.from_dict(dct)
                elif dct['type'] == LogEventType.LOG_EVENT_NAMED_EVENT:
                    return NamedEvent.from_dict(dct)
            return dct

        ev_arr = json.loads(json_str, object_hook=parse_log_event)
        log.events = ev_arr

        return log

    @staticmethod
    def load_from_file(filename: str) -> object:
        """
        loads a previously stored log from a file
        :param filename: the file to read the log from
        :return: a new Log object
        """
        json_str = ''
        with open(filename, 'r') as f:
            json_str = f.read()

        return Log.from_json(json_str)

