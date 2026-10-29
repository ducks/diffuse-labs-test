"""Public transport contract and an HTTP/1.0 adapter for local investigation.

await transport.open(name, payload) returns an async iterator of byte chunks.
UpstreamError means a retryable transport/provider failure. Other exceptions
are programming errors. Response.aclose() is idempotent and non-throwing.
An open() implementation cleans up partial resources if it raises/cancels.

HTTPTransport maps backend names to (host, port). It POSTs JSON and streams
Content-Length or connection-delimited bodies. This offline fixture deliberately
does not implement TLS, chunked encoding, provider auth, or a public HTTP server.
"""
import asyncio
import json


class UpstreamError(Exception):
    pass


class GatewayUnavailable(Exception):
    pass


class HTTPResponse:
    def __init__(self, reader, writer, length):
        self.reader, self.writer = reader, writer
        self.remaining = length
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed or self.remaining == 0:
            raise StopAsyncIteration
        try:
            chunk = await self.reader.read(4096 if self.remaining is None
                                           else min(4096, self.remaining))
        except (ConnectionError, OSError) as error:
            raise UpstreamError("upstream read failed") from error
        if not chunk:
            if self.remaining:
                raise UpstreamError("upstream truncated its response")
            raise StopAsyncIteration
        if self.remaining is not None:
            self.remaining -= len(chunk)
        return chunk

    async def aclose(self):
        if not self.closed:
            self.closed = True
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, OSError):
                pass


class HTTPTransport:
    def __init__(self, backends):
        self.backends = backends

    async def open(self, name, payload):
        writer = None
        try:
            reader, writer = await asyncio.open_connection(*self.backends[name])
            body = json.dumps(payload).encode()
            writer.write(b"POST /inference HTTP/1.0\r\nContent-Type: application/json\r\n"
                         + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
            await writer.drain()
            headers = await reader.readuntil(b"\r\n\r\n")
            lines = headers.split(b"\r\n")
            status = int(lines[0].split()[1])
            if status != 200:
                raise UpstreamError(f"upstream returned {status}")
            length = next((int(line.split(b":", 1)[1]) for line in lines[1:]
                           if line.lower().startswith(b"content-length:")), None)
            return HTTPResponse(reader, writer, length)
        except BaseException as error:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError):
                    pass
            if isinstance(error, (ConnectionError, OSError, asyncio.IncompleteReadError)):
                raise UpstreamError("upstream connection failed") from error
            raise
