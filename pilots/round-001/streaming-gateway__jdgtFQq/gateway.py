"""Streaming inference core. The HTTP layer forwards each yielded byte chunk."""
import asyncio

from transport import GatewayUnavailable, UpstreamError


async def _close_response(response):
    """Finish response cleanup even if the owner is cancelled again."""
    close_task = asyncio.ensure_future(response.aclose())
    cancellation = None
    while not close_task.done():
        try:
            await asyncio.shield(close_task)
        except asyncio.CancelledError as error:
            cancellation = error
    close_task.result()
    if cancellation is not None:
        raise cancellation


class Gateway:
    def __init__(self, transport, limits):
        if not limits or any(type(n) is not int or n < 1 for n in limits.values()):
            raise ValueError("backend limits must be positive integers")
        self.transport = transport
        self.limits = dict(limits)
        self.active = {name: 0 for name in limits}

    async def stream(self, payload):
        last_error = None
        for name, limit in self.limits.items():
            if self.active[name] >= limit:
                continue
            # No await between checking and reserving: admission is atomic on
            # the event loop, and each attempt owns exactly this reservation.
            self.active[name] += 1
            response = None
            committed = False
            try:
                response = await self.transport.open(name, payload)
                async for chunk in response:
                    if chunk:
                        committed = True
                    yield chunk
                return
            except UpstreamError as error:
                if committed:
                    raise
                last_error = error
            finally:
                try:
                    if response is not None:
                        await _close_response(response)
                finally:
                    self.active[name] -= 1
        raise GatewayUnavailable("no backend completed the request") from last_error
