import time
from dataclasses import dataclass
from socket import socket, AF_INET, SOCK_STREAM, timeout as SocketTimeout
from typing import Optional


@dataclass
class Measurement:
    """One reading, reported in the same format for every ammeter type."""
    ammeter: str                  # e.g. "greenlee"
    timestamp: float              # when the request was sent (seconds since epoch)
    value: Optional[float]        # current in amperes, or None if the reading failed
    error: Optional[str] = None   # reason for the failure, None if it succeeded

    @property
    def ok(self) -> bool:
        return self.value is not None


class AmmeterClient:
    """Talks to any ammeter. Brand differences (port, command) come from config.

    All three ammeters use the same pattern: send a command, get a number back.
    So one class configured per ammeter is enough. Adding a new ammeter means
    adding a block to config.yaml, with no new code.
    """

    def __init__(self, name: str, port: int, command, host: str = "localhost",
                 timeout: float = 2.0):
        self.name = name
        self.host = host
        self.port = port
        # Config files store the command as text, but sockets send bytes.
        self.command = command.encode("utf-8") if isinstance(command, str) else command
        self.timeout = timeout

    @classmethod
    def from_config(cls, name: str, config: dict) -> "AmmeterClient":
        """Build a client for the ammeter called `name` from the loaded config.yaml."""
        if name not in config["ammeters"]:
            known = ", ".join(config["ammeters"])
            raise ValueError(f"Unknown ammeter '{name}'. Configured ammeters: {known}")
        ammeter = config["ammeters"][name]
        testing = config["testing"]
        return cls(name, ammeter["port"], ammeter["command"],
                   host=testing["host"], timeout=testing["timeout_seconds"])

    def measure(self) -> Measurement:
        """Take one reading. Never raises: a failure is reported inside the result,
        so one bad reading cannot crash a long test run."""
        timestamp = time.time()
        try:
            with socket(AF_INET, SOCK_STREAM) as s:
                s.settimeout(self.timeout)   # a dead ammeter must not hang the test
                s.connect((self.host, self.port))
                s.sendall(self.command)
                data = s.recv(1024)
            if not data:
                # The emulator closes the connection silently on an unknown command.
                return Measurement(self.name, timestamp, None,
                                   "no reply (command not recognized?)")
            return Measurement(self.name, timestamp, float(data.decode("utf-8")))
        except SocketTimeout:
            return Measurement(self.name, timestamp, None,
                               f"timeout after {self.timeout}s")
        except ConnectionRefusedError:
            return Measurement(self.name, timestamp, None,
                               f"connection refused on port {self.port} (is it running?)")
        except ValueError:
            return Measurement(self.name, timestamp, None, "reply was not a number")
        except OSError as e:
            return Measurement(self.name, timestamp, None, f"network error: {e}")