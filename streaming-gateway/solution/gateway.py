"""Reference: reserve before awaits; commit on first bytes; always unwind."""
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
                        await response.aclose()
                finally:
                    self.active[name] -= 1
        raise GatewayUnavailable("no backend completed the request") from last_error
