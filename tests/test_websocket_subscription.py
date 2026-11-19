"""Exercise subscription authentication through the public connect operation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyControl4.error_handling import Unauthorized
from pyControl4.websocket import C4Websocket


@pytest.fixture
def connection():
    response = MagicMock()
    response.text = AsyncMock(return_value='{"subscriptionId":"subscription"}')
    response.json = AsyncMock(return_value={"subscriptionId": "subscription"})
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    session.get.return_value.__aexit__ = AsyncMock(return_value=False)
    restored = AsyncMock()
    ws = C4Websocket("192.168.1.1", session, restored)
    client = MagicMock()
    client.disconnect = AsyncMock()
    client.connect = AsyncMock()
    with patch(
        "pyControl4.websocket.socketio.AsyncClient", return_value=client
    ), patch.object(ws, "sio_disconnect", new_callable=AsyncMock), patch(
        "pyControl4.websocket.aiohttp.ClientSession", return_value=session
    ):
        yield ws, client, response, restored


async def start(connection):
    ws, client, _, _ = connection
    task = asyncio.create_task(ws.sio_connect("candidate-token"))
    await asyncio.sleep(0)
    namespace = client.register_namespace.call_args.args[0]
    namespace.emit = AsyncMock()
    return task, namespace


@pytest.mark.asyncio
async def test_transport_alone_is_not_success(connection):
    task, namespace = await start(connection)
    await namespace.on_connect()
    assert not task.done()
    connection[3].assert_not_awaited()
    await namespace.on_clientId("client")
    await task
    connection[3].assert_awaited_once()
    namespace.emit.assert_any_await("startSubscription", "subscription")


@pytest.mark.asyncio
async def test_subscription_rejection_reaches_connect_caller(connection):
    connection[2].text.return_value = (
        '{"error":"Unauthorized","details":"Insufficent permissions"}'
    )
    task, namespace = await start(connection)
    # Socket.IO invokes this in a different task after transport connect returns.
    await asyncio.create_task(namespace.on_clientId("client"))
    with pytest.raises(Unauthorized):
        await task
    connection[1].disconnect.assert_awaited_once()
    connection[3].assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_subscription_is_not_success(connection):
    connection[2].json.return_value = {}
    task, namespace = await start(connection)
    await namespace.on_clientId("client")
    with pytest.raises(ValueError, match="subscription ID"):
        await task
    connection[1].disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_subscription_timeout_cleans_up(connection):
    with patch("pyControl4.websocket._SUBSCRIPTION_TIMEOUT", 0.01):
        with pytest.raises(TimeoutError):
            await connection[0].sio_connect("token")
    connection[1].disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancellation_cleans_up(connection):
    task, _ = await start(connection)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    connection[1].disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnect_during_subscription_does_not_hang(connection):
    task, namespace = await start(connection)
    await namespace.on_disconnect()
    with pytest.raises(ConnectionError):
        await task
    connection[1].disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconnect_restores_only_after_authentication(connection):
    task, namespace = await start(connection)
    await namespace.on_clientId("first-client")
    await task
    await namespace.on_disconnect()
    await namespace.on_connect()
    assert connection[3].await_count == 1
    await namespace.on_clientId("second-client")
    assert connection[3].await_count == 2
