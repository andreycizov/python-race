import atexit
from typing import Optional, Any

from race.linearizer.client import TCPClient
from race.linearizer.proto import Input, Output

_SINGLETON_CLIENT: Optional[TCPClient] = None


def connect(host: str = '127.0.0.1', port: int = 50000) -> None:
    global _SINGLETON_CLIENT

    if _SINGLETON_CLIENT is not None:
        raise AssertionError

    client = TCPClient(
        host=host,
        port=port,
    )
    client.connect()

    _SINGLETON_CLIENT = client

    atexit.register(disconnect)


def client() -> TCPClient:
    if _SINGLETON_CLIENT is None:
        raise AssertionError

    return _SINGLETON_CLIENT


def query(value: Any) -> Any:
    c = client()
    c.send(Input(origin=-1, value=value))
    response = c.recv()

    if not isinstance(response, Output):
        raise AssertionError(response)

    return response.value


def disconnect():
    global _SINGLETON_CLIENT

    if _SINGLETON_CLIENT is None:
        raise AssertionError

    _SINGLETON_CLIENT.close()
    _SINGLETON_CLIENT = None
