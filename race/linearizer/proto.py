import struct
from typing import Optional, Tuple, Any, NewType

import dill
from dataclasses import dataclass

PACK_FMT = 'L'
PACK_SIZE = struct.calcsize(PACK_FMT)


def pack_str(body: str) -> bytes:
    body = body.encode()
    size = len(body)

    return struct.pack(PACK_FMT, size) + body


def unpack_str(body: bytes) -> Optional[Tuple[str, int]]:
    if len(body) < PACK_SIZE:
        return None
    size, = struct.unpack(PACK_FMT, body[:PACK_SIZE])

    if len(body) < PACK_SIZE + size:
        return None
    else:
        str_body = body[PACK_SIZE:PACK_SIZE + size]

        return str_body.decode(), PACK_SIZE + size


@dataclass
class Packet:
    origin: 'ConnId'

    @classmethod
    def from_str(cls, body: str) -> 'Packet':
        return dill.loads(body)

    def into_str(self) -> str:
        return dill.dumps(self)


class Reset(Packet):
    pass


class Terminate(Packet):
    pass


@dataclass
class Input(Packet):
    value: Any


@dataclass
class Output(Packet):
    value: Any


ConnId = NewType('ConnId', int)
