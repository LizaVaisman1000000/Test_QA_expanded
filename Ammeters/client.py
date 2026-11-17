from socket import socket, AF_INET, SOCK_STREAM, timeout as SocketTimeout


# Changed: the original function only printed the value and returned nothing.
# It now returns the current as a float (or None on failure), so the sampling
# and statistics code can use the numbers. A timeout parameter was also added.
def request_current_from_ammeter(port: int, command: bytes, timeout: float = 2.0):
    """Request one measurement from an ammeter emulator.

    Returns the current as a float, or None if the request failed.
    """
    # Added: try/except, so one failed request (emulator down, bad data)
    # does not crash the whole test run.
    try:
        with socket(AF_INET, SOCK_STREAM) as s:
            # Added: without a timeout, a stuck or dead emulator would make
            # connect/recv wait forever and hang the test.
            s.settimeout(timeout)
            s.connect(('localhost', port))
            s.sendall(command)
            data = s.recv(1024)

            # The emulator closes the connection without a reply when the
            # command does not match exactly (see base_ammeter.py), so empty
            # data most likely means "command not recognized".
            if not data:
                print(f"Port {port}: no data received (command not recognized?)")
                return None

            # Added: convert the text reply to a number so it can be analyzed.
            # A malformed reply raises ValueError, handled below.
            value = float(data.decode('utf-8'))
            print(f"Received current measurement from port {port}: {value} A")
            return value

    # Handled cases: nothing listening on the port (ConnectionRefusedError),
    # no reply in time (SocketTimeout), reply that is not a number (ValueError),
    # and any other network problem (OSError). Returning None lets the caller
    # decide whether to retry, skip the sample, or report an error.
    except (ConnectionRefusedError, SocketTimeout, ValueError, OSError) as e:
        print(f"Port {port}: request failed - {e}")
        return None