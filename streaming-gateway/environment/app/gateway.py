"""Streaming inference core. The HTTP layer forwards each yielded byte chunk."""
from transport import GatewayUnavailable, UpstreamError


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
            self.active[name] += 1
            try:
                response = await self.transport.open(name, payload)
                async for chunk in response:
                    yield chunk
                await response.aclose()
                self.active[name] -= 1
                return
            except UpstreamError as error:
                # A different backend may still be healthy.
                last_error = error
                continue
        raise GatewayUnavailable("no backend completed the request") from last_error
