# no leader election, start election
# if timeout - start election
# no timeout -
import dataclasses
from collections import deque
from typing import TypeVar, Generic

from race2.abstract import ProcessGenerator

# - lost messages
# - lost workers
# - communication

M = TypeVar("M")


@dataclasses.dataclass
class Channel(Generic[M]):
    queue: deque[M] = dataclasses.field(default_factory=deque)

    def send(self, message: M) -> None:
        self.queue.append(message)

    def recv(self) -> M | None:
        if len(self.queue):
            return self.queue.popleft()
        else:
            return None


class Message:
    pass


@dataclasses.dataclass
class Prepare(Message):
    number: int


@dataclasses.dataclass
class Promise(Message):
    number: int
    previous: "AcceptedValue | None"


@dataclasses.dataclass
class AcceptedValue:
    number: int
    value: int


@dataclasses.dataclass
class Accept(Message):
    value: AcceptedValue


@dataclasses.dataclass
class AcceptedNack(Message):
    number: int


@dataclasses.dataclass
class Accepted(Message):
    value: AcceptedValue


@dataclasses.dataclass
class PromiseNack(Message):
    number: int


def acceptor(process_id: int, channel: Channel[Message]) -> ProcessGenerator:
    last_promised_number: int | None = None
    last_accepted: AcceptedValue | None = None

    another_channel: Channel[Message]
    while True:
        yield "recv"
        match channel.recv():
            case Prepare(n):
                if last_promised_number is not None or last_promised_number < n:
                    yield "prepare-promise"
                    another_channel.send(Promise(n, last_accepted))
                else:
                    yield "prepare-promise-nack"
                    another_channel.send(PromiseNack(n))
            case Accept(value=value):
                if last_promised_number <= value.number:
                    yield "accept-ack"
                    last_accepted = value
                    # send to every acceptor and every learner
                    another_channel.send(Accepted(value))
                    pass

                else:
                    yield "accept-nack"
                    another_channel.send(AcceptedNack(last_promised_number))
            case None:
                pass


def process(event: None):
    state = None
    match state:
        case LeaderElection():
            match event:
                case Heartbeat:
                    pass
        case Leader():
            pass
        case Follower():
            pass
    pass
