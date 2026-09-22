"""Session-scoped, same-UID Unix socket; no network listener or shell commands."""
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import tempfile
import threading
import time

from scheduler import SchedulerError

MAX_REQUEST = 65536
MAX_RESPONSE = 8 * 1024 * 1024


def read_message(connection, limit):
    data = bytearray()
    while b"\n" not in data:
        block = connection.recv(min(8192, limit + 1 - len(data)))
        if not block:
            raise SchedulerError("Scheduler connection closed before a complete response")
        data.extend(block)
        if len(data) > limit:
            raise SchedulerError("Scheduler message is too large")
    line, remainder = data.split(b"\n", 1)
    if remainder:
        raise SchedulerError("Only one request is permitted per connection")
    return json.loads(line.decode("utf-8"))


def call(path, request):
    data = json.dumps(request).encode("utf-8") + b"\n"
    if len(data) > MAX_REQUEST:
        raise SchedulerError("Scheduler request is too large")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(55)
            connection.connect(path)
            connection.sendall(data)
            result = read_message(connection, MAX_RESPONSE)
    except (OSError, ValueError, SchedulerError) as exc:
        raise SchedulerError("Host scheduler connection failed: {}. Check the host queue before retrying a submission; no automatic retry was made.".format(exc))
    if (not isinstance(result, dict) or set(result) != {"returncode", "stdout", "stderr"}
            or not isinstance(result["returncode"], int)
            or not all(isinstance(result[key], str) for key in ("stdout", "stderr"))):
        raise SchedulerError("Invalid response from host scheduler; check your queue before retrying")
    return result


class HostJobs:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.directory = None
        self.server = None
        self.thread = None
        self.stop = threading.Event()
        self.capacity = threading.BoundedSemaphore(4)
        self.workers = []

    def __enter__(self):
        if not hasattr(socket, "SO_PEERCRED"):
            raise SchedulerError("Host job connections require Linux peer-credential support")
        self.directory = Path(tempfile.mkdtemp(prefix="ws-jobs-", dir="/tmp"))
        os.chmod(str(self.directory), 0o700)
        try:
            self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server.bind(str(self.directory / "scheduler.sock"))
            os.chmod(str(self.directory / "scheduler.sock"), 0o600)
            self.server.listen(8)
            self.server.settimeout(0.2)
            self.thread = threading.Thread(target=self._serve, daemon=True)
            self.thread.start()
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def _serve(self):
        while not self.stop.is_set():
            try:
                connection, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            # Do not queue submissions behind a slow client and execute them
            # after the caller has already timed out.
            if not self.capacity.acquire(blocking=False):
                with connection:
                    connection.settimeout(1)
                    try:
                        read_message(connection, MAX_REQUEST)
                    except (OSError, ValueError, SchedulerError):
                        pass
                    self._reply(connection, {"returncode": 2, "stdout": "", "stderr":
                                "ws: Host scheduler connection is busy; this request was not submitted.\n"})
                continue
            self.workers = [worker for worker in self.workers if worker.is_alive()]
            worker = threading.Thread(target=self._handle, args=(connection,), daemon=True)
            self.workers.append(worker)
            worker.start()

    @staticmethod
    def _reply(connection, result):
        try:
            connection.sendall(json.dumps(result).encode("utf-8") + b"\n")
        except OSError:
            pass  # Never retry a submission after a disconnected client.

    def _handle(self, connection):
        try:
            with connection:
                connection.settimeout(3)
                try:
                    _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != os.getuid():
                        raise SchedulerError("Host scheduler connection requires the same user identity")
                    request = read_message(connection, MAX_REQUEST)
                    result = self.scheduler.request(request)
                except (SchedulerError, OSError, ValueError, TypeError, KeyError) as exc:
                    result = {"returncode": 2, "stdout": "", "stderr": "ws: " + str(exc) + "\n"}
                self._reply(connection, result)
        finally:
            self.capacity.release()

    def __exit__(self, *unused):
        self.stop.set()
        if self.server is not None:
            self.server.close()
        if self.thread is not None:
            self.thread.join(timeout=2)
        deadline = time.monotonic() + 48
        for worker in self.workers:
            worker.join(timeout=max(0, deadline - time.monotonic()))
        if self.directory is not None:
            shutil.rmtree(str(self.directory))
