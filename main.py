import threading
import time

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.client import request_current_from_ammeter


def run_greenlee_emulator():
    GreenleeAmmeter(5000).start_server()

def run_entes_emulator():
    EntesAmmeter(5001).start_server()

def run_circutor_emulator():
    CircutorAmmeter(5002).start_server()

if __name__ == "__main__":
    threading.Thread(target=run_greenlee_emulator, daemon=True).start()
    threading.Thread(target=run_entes_emulator, daemon=True).start()
    threading.Thread(target=run_circutor_emulator, daemon=True).start()

    time.sleep(5)  # give the servers time to start
    # Ports and commands follow the README. Original code used shifted ports
    # (5001-5003) and truncated commands, so the emulators silently ignored requests.

    # Request a measurement from Greenlee (README port 5000). The original code used
    # port 5001 and sent only b'MEASURE_GREENLEE'. The emulator compares the request
    # to its full command exactly (see base_ammeter.py), so it ignored the incomplete one.
    request_current_from_ammeter(5000, b'MEASURE_GREENLEE -get_measurement') 
    # Request a measurement from ENTES (README port 5001). The original code used
    # port 5002 and sent only b'MEASURE_ENTES'. The emulator compares the request
    # to its full command exactly (see base_ammeter.py), so it ignored the incomplete one.
    request_current_from_ammeter(5001, b'MEASURE_ENTES -get_data')
    # Request a measurement from Circutor (README port 5002). The original code used
    # port 5003 and sent only b'MEASURE_CIRCUTOR'. The emulator compares the request
    # to its full command exactly (see base_ammeter.py), so it ignored the incomplete one.
    request_current_from_ammeter(5002, b'MEASURE_CIRCUTOR -get_measurement')