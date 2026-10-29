"""Behavioral verifier with event-driven failures and a real localhost HTTP test."""
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, os.environ.get("SERVICE_DIR", "/opt/task-service"))
from transport import GatewayUnavailable, HTTPTransport, UpstreamError

spec = importlib.util.spec_from_file_location(
    "candidate_gateway", os.environ.get("GATEWAY_PATH", "/app/gateway.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Gateway = module.Gateway


class Gate:
    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def wait(self):
        self.entered.set()
        await self.release.wait()


class Response:
    def __init__(self, *events):
        self.events = list(events)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed:
            raise AssertionError("read from closed response")
        while self.events:
            event = self.events.pop(0)
            if isinstance(event, Gate):
                await event.wait()
            elif isinstance(event, Exception):
                raise event
            else:
                return event
        raise StopAsyncIteration

    async def aclose(self):
        self.closed = True


class Transport:
    def __init__(self, **scripts):
        self.scripts = {name: list(events) for name, events in scripts.items()}
        self.requests = []
        self.responses = []

    async def open(self, name, payload):
        self.requests.append((name, copy.deepcopy(payload)))
        if not self.scripts[name]:
            raise AssertionError(f"unexpected extra request to {name}")
        event = self.scripts[name].pop(0)
        if isinstance(event, Gate):
            await event.wait()
            event = self.scripts[name].pop(0)
        if isinstance(event, Exception):
            raise event
        self.responses.append(event)
        return event


async def collect(stream):
    return b"".join([chunk async for chunk in stream])


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    def setup_gateway(self, transport, limits=None):
        gateway = Gateway(transport, limits or {"primary": 1, "fallback": 1})
        self.addAsyncCleanup(self.check_released, gateway, transport)
        return gateway

    async def check_released(self, gateway, transport):
        self.assertEqual(gateway.active, {name: 0 for name in gateway.limits},
                         "capacity leaked or released twice")
        self.assertTrue(all(r.closed for r in transport.responses), "upstream leaked")

    async def test_open_failure_falls_back(self):
        transport = Transport(primary=[UpstreamError("503")], fallback=[Response(b"ok")])
        gateway = self.setup_gateway(transport)
        self.assertEqual(await collect(gateway.stream({"model": "a"})), b"ok")
        self.assertEqual([r[0] for r in transport.requests], ["primary", "fallback"])

    async def test_failure_before_body_falls_back(self):
        transport = Transport(primary=[Response(b"", UpstreamError("reset"))],
                              fallback=[Response(b"healthy")])
        gateway = self.setup_gateway(transport)
        self.assertEqual(await collect(gateway.stream({})), b"healthy")

    async def test_partial_stream_error_is_visible_and_never_retried(self):
        failure = UpstreamError("connection dropped")
        transport = Transport(primary=[Response(b"data: partial\n\n", failure)],
                              fallback=[Response(b"wrong answer")])
        gateway = self.setup_gateway(transport)
        stream = gateway.stream({})
        self.assertEqual(await anext(stream), b"data: partial\n\n")
        with self.assertRaises(UpstreamError) as raised:
            await anext(stream)
        self.assertIs(raised.exception, failure)
        self.assertEqual(len(transport.requests), 1)

    async def test_first_chunk_does_not_wait_for_completion(self):
        gate = Gate()
        transport = Transport(primary=[Response(b"first", gate, b"last")])
        gateway = self.setup_gateway(transport)
        stream = gateway.stream({})
        try:
            self.assertEqual(await asyncio.wait_for(anext(stream), 2), b"first")
            gate.release.set()
            self.assertEqual(await collect(stream), b"last")
        finally:
            gate.release.set()
            await stream.aclose()

    async def test_preserves_fragmented_sse_and_payload(self):
        chunks = [b"da", b'ta: {"text":"', b"\xe2", b"\x98\x83", b'"}\n', b"\n",
                  b"data: [DONE]\n\n"]
        payload = {"messages": [{"role": "user", "content": "hello"}], "stream": True}
        original = copy.deepcopy(payload)
        transport = Transport(primary=[Response(*chunks)])
        gateway = self.setup_gateway(transport)
        self.assertEqual(await collect(gateway.stream(payload)), b"".join(chunks))
        self.assertEqual(payload, original)
        self.assertEqual(transport.requests, [("primary", original)])

    async def test_clean_empty_response_is_success(self):
        transport = Transport(primary=[Response(b"", b"")], fallback=[Response(b"wrong")])
        gateway = self.setup_gateway(transport)
        self.assertEqual(await collect(gateway.stream({})), b"")
        self.assertEqual(len(transport.requests), 1)

    async def test_cancellation_while_opening_releases_capacity(self):
        gate = Gate()
        transport = Transport(primary=[gate, Response(b"unused")])
        gateway = self.setup_gateway(transport)
        pending = asyncio.create_task(collect(gateway.stream({})))
        await asyncio.wait_for(gate.entered.wait(), 2)
        self.assertEqual(gateway.active["primary"], 1)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertEqual(len(transport.requests), 1)

    async def test_cancellation_while_reading_closes_response(self):
        gate = Gate()
        transport = Transport(primary=[Response(gate, b"unused")])
        gateway = self.setup_gateway(transport)
        pending = asyncio.create_task(collect(gateway.stream({})))
        await asyncio.wait_for(gate.entered.wait(), 2)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending

    async def test_early_generator_close_releases_only_its_own_slot(self):
        transport = Transport(primary=[Response(b"one", b"rest"), Response(b"two", b"rest")])
        gateway = self.setup_gateway(transport, {"primary": 2})
        first, second = gateway.stream({}), gateway.stream({})
        try:
            self.assertEqual(await anext(first), b"one")
            self.assertEqual(await anext(second), b"two")
            self.assertEqual(gateway.active["primary"], 2)
            await first.aclose()
            self.assertEqual(gateway.active["primary"], 1)
            self.assertFalse(transport.responses[1].closed)
            self.assertEqual(await collect(second), b"rest")
        finally:
            await first.aclose()
            await second.aclose()

    async def test_open_reservation_prevents_oversubscription(self):
        gate = Gate()
        transport = Transport(primary=[gate, Response(b"primary")],
                              fallback=[Response(b"fallback")])
        gateway = self.setup_gateway(transport)
        first = asyncio.create_task(collect(gateway.stream({"request": 1})))
        try:
            await asyncio.wait_for(gate.entered.wait(), 2)
            self.assertEqual(await collect(gateway.stream({"request": 2})), b"fallback")
            self.assertEqual(gateway.active, {"primary": 1, "fallback": 0})
            gate.release.set()
            self.assertEqual(await first, b"primary")
        finally:
            gate.release.set()
            await first

    async def test_all_busy_does_not_send_requests(self):
        transport = Transport(primary=[Response(b"one", b"end")])
        gateway = self.setup_gateway(transport, {"primary": 1})
        first = gateway.stream({})
        try:
            await anext(first)
            with self.assertRaises(GatewayUnavailable):
                await collect(gateway.stream({}))
            self.assertEqual(len(transport.requests), 1)
        finally:
            await first.aclose()

    async def test_all_providers_fail_then_next_request_can_succeed(self):
        transport = Transport(primary=[UpstreamError("unavailable"), Response(b"recovered")],
                              fallback=[Response(UpstreamError("empty failure"))])
        gateway = self.setup_gateway(transport)
        with self.assertRaises(GatewayUnavailable):
            await collect(gateway.stream({}))
        self.assertEqual(gateway.active, {"primary": 0, "fallback": 0})
        self.assertEqual(await collect(gateway.stream({})), b"recovered")

    async def test_programming_error_is_not_retried(self):
        failure = ValueError("bug in adapter")
        transport = Transport(primary=[failure], fallback=[Response(b"wrong")])
        gateway = self.setup_gateway(transport)
        with self.assertRaises(ValueError) as raised:
            await collect(gateway.stream({}))
        self.assertIs(raised.exception, failure)
        self.assertEqual(len(transport.requests), 1)

    async def test_non_default_backend_names(self):
        transport = Transport(east=[UpstreamError("down")], west=[Response(b"ok")])
        gateway = self.setup_gateway(transport, {"east": 2, "west": 3})
        self.assertEqual(await collect(gateway.stream({})), b"ok")

    async def test_constructor_validation(self):
        for limits in ({}, {"a": 0}, {"a": -1}, {"a": True}, {"a": 1.5}):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                Gateway(Transport(), limits)

    async def test_real_http_fallback_streams_before_server_finishes(self):
        release, finished = asyncio.Event(), asyncio.Event()
        requests = []

        async def provider(reader, writer, fail):
            try:
                headers = await reader.readuntil(b"\r\n\r\n")
                length = next(int(line.split(b":")[1]) for line in headers.split(b"\r\n")
                              if line.lower().startswith(b"content-length:"))
                requests.append((fail, await reader.readexactly(length)))
                if fail:
                    writer.write(b"HTTP/1.0 503 Unavailable\r\nContent-Length: 0\r\n\r\n")
                else:
                    writer.write(b"HTTP/1.0 200 OK\r\nContent-Length: 10\r\n\r\nfirst")
                    await writer.drain()
                    await release.wait()
                    writer.write(b" last")
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
                if not fail:
                    finished.set()

        bad = await asyncio.start_server(lambda r, w: provider(r, w, True), "127.0.0.1", 0)
        good = await asyncio.start_server(lambda r, w: provider(r, w, False), "127.0.0.1", 0)
        transport = HTTPTransport({"primary": bad.sockets[0].getsockname(),
                                   "fallback": good.sockets[0].getsockname()})
        gateway = Gateway(transport, {"primary": 1, "fallback": 1})
        stream = gateway.stream({"model": "fixture"})
        try:
            self.assertEqual(await asyncio.wait_for(anext(stream), 2), b"first")
            self.assertFalse(finished.is_set())
            release.set()
            self.assertEqual(await collect(stream), b" last")
            self.assertEqual([r[0] for r in requests], [True, False])
            self.assertEqual(requests[0][1], requests[1][1])
            self.assertEqual(gateway.active, {"primary": 0, "fallback": 0})
        finally:
            release.set()
            await stream.aclose()
            bad.close()
            good.close()
            await bad.wait_closed()
            await good.wait_closed()
            await asyncio.wait_for(finished.wait(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
