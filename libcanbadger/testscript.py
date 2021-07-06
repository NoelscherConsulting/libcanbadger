
from libcanbadger.canbadger import CANBadger
from libcanbadger.uds.session import Session, SessionStatus
from libcanbadger.search.bruteforce_strategy import BruteforceStrategy
from libcanbadger.search.search import Search
from libcanbadger.search.integer_range_parameter import IntegerRangeParameter
from libcanbadger.iso_tp.iso_tp_handler import IsoTpHandler, IsoTpMessage
from libcanbadger.canbadger_connection_process import discover_canbadgers
from libcanbadger.util.can_settings import CANBadgerSettings, CanbadgerStatusBits
from libcanbadger.interface import LoggedInterface
import sys
import time


def main():
    # discover canbadgers
    # cbs = discover_canbadgers()
    # print(cbs)

    cb = CANBadger("10.0.0.180")

    if not cb.connect():
        print("Didn't connect...")
        quit(-1)

    settings = CANBadgerSettings()
    settings.set_status_bit(CanbadgerStatusBits.CAN1_LOGGING)
    settings.set_status_bit(CanbadgerStatusBits.CAN1_INT_ENABLED)
    settings.set_status_bit(CanbadgerStatusBits.CAN1_STANDARD)
    settings.can1_speed = 500000
    settings.can2_speed = 500000
    settings.spi_speed = 20000000
    cb.configure(settings)

    # turn on / off the GPIOs like this
    # cb.set_gpio(gpio_num=2, state=True)
    # time.sleep(1)
    # cb.set_gpio(gpio_num=2, state=False)

    try:
        li = LoggedInterface(underlying=cb)
        # start receiving/transmitting - this is important
        li.start()
        # start logging
        log = li.start_log("test_log")
        with Session(interface=li, tester_id=0x710, ecu_id=0x77a, use_padding=True, padding=0xAA) as session:
            session.start(timeout=3) # this will request a diagnostic session
            if session.status != SessionStatus.Failed:
                search = Search(strategy=BruteforceStrategy())
                search.add_param(IntegerRangeParameter('data_id', start=0x0ff0, stop=0x0fff, step=1))
                scnt = 0
                nscnt = 0
                ttcnt = 0
                while search.progress() < 1.0:
                    time.sleep(0.001)
                    id_to_check = search.next()[0]
                    success, data = session.request_data_by_id(id_to_check)
                    if success:
                        scnt += 1
                        print(f"For ID {id_to_check} we got the response {data}")
                    else:
                        nscnt += 1
                    ttcnt += 1
                print(f"Out of {ttcnt} checked ids total, we got {scnt} hits and {nscnt} misses")
        li.stop_log(log)
        print("Logged data:")
        log.pretty_print()

    except Exception as e:
        print(f"{sys.exc_info()[0]}\n{sys.exc_info()[1]}\n{sys.exc_info()[2].tb_lineno}")

        raise e
    finally:
        cb.send_stop()
        cb.reset()

    '''
    ith = IsoTpHandler(interface=cb)
    ith.send_data(0x111, b'\x11\x22\x33\x44\x55\x66\x77\x88\x99\x00')

    cb.send_stop()
    cb.reset()
    '''


if __name__ == "__main__":
    main()
