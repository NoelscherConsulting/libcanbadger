from libcanbadger.interface import Interface, LoggedInterface
from libcanbadger.log import Log, LogEventType, FrameEvent, NamedEvent
from libcanbadger.frame import Frame

class MockInterface(Interface):
    def __init__(self):
        self.rx_frames = []
        self.tx_frames = []

    def send_frame(self, frame, blocking=True) -> bool:
        self.tx_frames.append(frame)
        return True

    def receive_frame(self, timeout=0) -> Frame:
        return self.rx_frames.pop(-1)




def test_logged_interface():
    mi = MockInterface()
    interface = LoggedInterface(underlying=mi)
    assert(len(interface.logs) == 0)
    assert(interface.underlying == mi)

    # it should start new logs
    log = interface.start_log('test_log')
    assert(log is not None)
    assert(log.name == 'test_log')
    assert(len(log.events) == 0)

    # it should log received messages
    mi.rx_frames.append(Frame(arb_id=0x123, payload=b'\x12\x23'))
    interface.receive_frame()
    assert(len(log.events) == 1)
    assert(log.events[0].type == LogEventType.LOG_EVENT_RX_FRAME)
    assert(log.events[0].frame.arb_id == 0x123)
    assert(log.events[0].frame.payload == b'\x12\x23')

    # it should log transmitted messages
    interface.send_frame(Frame(arb_id=0x321, payload=b'\x55\x55'))
    assert(len(log.events) == 2)
    assert(log.events[1].type == LogEventType.LOG_EVENT_TX_FRAME)
    assert(log.events[1].frame.arb_id == 0x321)
    assert(log.events[1].frame.payload == b'\x55\x55')

    # it should stop new logs
    interface.stop_log(log)
    assert(len(interface.logs) == 0)
    assert(len(interface.log_to_status_map.keys()) == 0)

def test_log():
    log = Log()

    # it should log frame events
    log.log(FrameEvent(Frame(arb_id=0x123, payload=b'\x00'), type=LogEventType.LOG_EVENT_RX_FRAME))
    log.log(FrameEvent(Frame(arb_id=0x123, payload=b'\x00'), type=LogEventType.LOG_EVENT_TX_FRAME))
    assert(len(log.events) == 2)

    # it should log named events
    log.log(NamedEvent(name="test named event"))
    assert (len(log.events) == 3)
    assert(isinstance(log.events[-1], NamedEvent))

    # it should serialize to json
    json_str = log.to_json()
    assert(len(json_str) > 0)

    # it should parse json into a Log
    parsed_log = Log.from_json(json_str)
    assert(len(parsed_log.events) == 3)
    assert(isinstance(log.events[-1], NamedEvent))

    # it should allow iterating over events
    last_e = None
    for e in parsed_log:
        assert(e is not None)
        last_e = e
    assert(last_e == parsed_log.events[-1])

