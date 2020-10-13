# cross-process linearisation routines
# - many processes connect to a single process
# - connections must be TCP otherwise Queue may be an issue (for killed processes)
# - The Root Process gets a control

# - we could just combine threads with processes (?)
# - basically just read in a Thread. Thread can also get passed
#   a socket from process that it takes care of fully
import logging
import select
import socket
from collections import deque
from typing import Optional, List, Dict, Deque, Iterable

from dataclasses import dataclass, field, replace

from race.linearizer.proto import pack_str, unpack_str, Packet, Terminate, ConnId

_LOG = logging.getLogger(__name__)


@dataclass
class TCPServer:
    listen_socket: Optional[socket.socket] = None

    client_conn_ids: ConnId = ConnId(0)

    client_sockets_fw: Dict[socket.socket, ConnId] = field(default_factory=dict)
    client_sockets_bk: Dict[ConnId, socket.socket] = field(default_factory=dict)

    client_buffers_read: Dict[ConnId, bytes] = field(default_factory=dict)
    client_buffers_write: Dict[ConnId, bytes] = field(default_factory=dict)

    read_size: int = 4096

    in_queue: Deque[Packet] = field(default_factory=deque)

    def init_listen(self) -> None:
        if self.listen_socket is not None:
            raise AssertionError

        new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_socket.bind(('localhost', 50000))
        self.listen_socket = new_socket
        self.listen_socket.setblocking(False)
        self.listen_socket.listen(0)

    def client_accept(self, conn_socket: socket.socket) -> None:
        conn_id = self.client_conn_ids
        self.client_conn_ids += 1

        self.client_sockets_fw[conn_socket] = conn_id
        self.client_sockets_bk[conn_id] = conn_socket

        self.client_buffers_read[conn_id] = bytes()
        self.client_buffers_write[conn_id] = bytes()

    def client_disconnected(self, client_id: ConnId, reason: Optional[str] = None) -> None:
        _LOG.info('disco %s %s', client_id, reason)
        client_socket = self.client_sockets_bk[client_id]

        del self.client_sockets_fw[client_socket]
        del self.client_sockets_bk[client_id]
        del self.client_buffers_read[client_id]
        del self.client_buffers_write[client_id]

    def client_received(self, client_id: ConnId) -> None:
        curr_buffer = self.client_buffers_read[client_id]
        unpacked = unpack_str(curr_buffer)

        if unpacked is None:
            return

        body, offset = unpacked

        self.client_buffers_read[client_id] = curr_buffer[offset:]
        packet_body = Packet.from_str(body)
        packet_body = replace(packet_body, origin=client_id)
        self.in_queue.append(packet_body)

    @property
    def inputs(self) -> List[socket.socket]:
        return [self.listen_socket] + list(self.client_sockets_fw.keys())

    @property
    def outputs(self) -> List[socket.socket]:
        return [self.client_sockets_bk[x] for x, v in self.client_buffers_write.items() if len(v)]

    def dispatch_readable(self, x: socket.socket) -> None:
        if x == self.listen_socket:
            new_socket, _ = self.listen_socket.accept()
            self.client_accept(conn_socket=new_socket)
        else:
            conn_id = self.client_sockets_fw[x]

            buffer_body = x.recv(self.read_size)

            if len(buffer_body) == 0:
                self.client_disconnected(conn_id, 'readable')
                return

            self.client_buffers_read[conn_id] += buffer_body

            self.client_received(conn_id)

    def dispatch_writable(self, x: socket.socket) -> None:
        conn_id = self.client_sockets_fw[x]

        buffer_body = self.client_buffers_write[conn_id]

        sent_size = x.send(buffer_body)

        if sent_size == 0:
            self.client_disconnected(conn_id, 'writable')
            return

        self.client_buffers_write[conn_id] = buffer_body[sent_size:]

    def dispatch_exceptional(self, x: socket.socket) -> None:
        conn_id = self.client_sockets_fw[x]

        self.client_disconnected(conn_id, 'exceptional')

    def loop_once(self) -> None:
        readable: List[socket.socket]
        writable: List[socket.socket]
        exceptional: List[socket.socket]
        readable, writable, exceptional = select.select(
            self.inputs, self.outputs, self.inputs
        )

        for x in readable:
            self.dispatch_readable(x)

        for x in writable:
            self.dispatch_writable(x)

        for x in exceptional:
            self.dispatch_exceptional(x)

    def open(self) -> None:
        self.init_listen()

    def close(self) -> None:
        self.listen_socket.close()
        self.listen_socket = None

        for k in self.client_sockets_bk.keys():
            self.client_disconnected(k)

        self.in_queue = deque()

    def __enter__(self):
        self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def send(self, packet: Packet) -> None:
        buffer = pack_str(packet.into_str())

        self.client_buffers_write[packet.origin] += buffer

    def execute(self) -> Iterable[Packet]:
        while True:
            self.loop_once()

            while len(self.in_queue):
                next_item = self.in_queue.popleft()

                if isinstance(next_item, Terminate):
                    return
                else:
                    yield next_item
