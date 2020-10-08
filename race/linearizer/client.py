import socket
from typing import Optional

from dataclasses import dataclass

from race.linearizer.proto import Packet, pack_str, unpack_str


@dataclass
class TCPClient:
    host: str
    port: int

    client_socket: Optional[socket.socket] = None

    recv_buffer_size: int = 4096

    def init_socket(self) -> None:
        if self.client_socket is not None:
            raise AssertionError

        new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_socket.connect((self.host, self.port))

        self.client_socket = new_socket

    def connect(self) -> None:
        self.init_socket()

    def close(self) -> None:
        if self.client_socket is None:
            raise AssertionError

        self.client_socket.close()
        self.client_socket = None

    def send(self, packet: Packet) -> None:
        self.client_socket.send(pack_str(packet.into_str()))

    def recv(self) -> Packet:
        full_buffer = bytes()

        while True:
            full_buffer += self.client_socket.recv(self.recv_buffer_size)

            unpacked = unpack_str(full_buffer)

            if not unpacked:
                continue

            body_str, offset = unpacked

            leftover_size = len(full_buffer[offset:])
            if leftover_size:
                raise AssertionError(leftover_size)

            return Packet.from_str(body=body_str)
