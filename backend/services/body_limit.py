"""A hard ceiling on request body size, enforced at the ASGI edge.

Why this can't live in the route handlers: FastAPI parses the multipart form
BEFORE it solves dependencies (fastapi/routing.py — `body = await
request.form()` runs well above the `solve_dependencies` call), and Starlette's
multipart parser applies its `max_part_size` only to non-file parts
(starlette/formparsers.py, the `if self._current_part.file is None` branch).
A part carrying a filename gets a SpooledTemporaryFile with NO upper bound.

So by the time `upload_resume` executes its first line, an arbitrarily large
body has already been written to the container's temp storage, and it happened
before the authentication dependency ran — i.e. anonymously. No check inside a
handler can reach that; the per-route `file.size` checks are the second layer,
not the first.

This middleware is the first layer. It is a pure ASGI middleware rather than a
BaseHTTPMiddleware subclass because BaseHTTPMiddleware buffers the body, which
is the exact thing being prevented.
"""

from starlette.datastructures import Headers


DEFAULT_MAX_BODY_BYTES = 4 * 1024 * 1024  # 4 MB

# Both upload routes cap at 2 MB and they are the only UploadFile routes in the
# app; everything else takes small JSON. The default above is that 2 MB plus
# room for multipart overhead — deliberately not much more, since the whole
# point is that nothing legitimate is anywhere near it.
TOO_LARGE_DETAIL = "Request body is too large."


class BodyTooLarge(Exception):
    """Raised from the wrapped receive() when a streamed body exceeds the cap.

    Purely internal: the middleware catches it again itself. It deliberately
    does NOT rely on an exception handler registered on the app, because it
    would not reliably get one — FastAPI wraps form parsing in a broad
    `except Exception` that re-raises everything as HTTPException(400, "There
    was an error parsing the body") (fastapi/routing.py). Cutting the stream
    off mid-parse trips exactly that clause, so a chunked oversized upload
    would be reported to the client as a malformed request rather than as too
    large. Owning the response in the middleware sidesteps the question.
    """


async def _send_413(send) -> None:
    body = b'{"detail":"' + TOO_LARGE_DETAIL.encode() + b'"}'
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = DEFAULT_MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast path: an honest Content-Length lets us reject without calling the
        # app at all, so the form parser never runs and nothing touches disk.
        # This covers every ordinary client.
        content_length = Headers(scope=scope).get("content-length")
        if content_length and content_length.isdigit():
            if int(content_length) > self.max_bytes:
                await _send_413(send)
                return

        # Slow path: a chunked request carries no Content-Length, so the only
        # way to know the size is to count as it arrives.
        received = 0
        too_large = False
        response_started = False

        async def counting_receive():
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    too_large = True
                    raise BodyTooLarge()
            return message

        async def guarded_send(message):
            nonlocal response_started
            # Once the cap is blown we own the response. Anything the app
            # produces from here describes the truncation it just hit, not the
            # reason for it — FastAPI in particular renders the aborted form
            # parse as 400 "There was an error parsing the body". Drop it; the
            # real 413 goes out below.
            if too_large and not response_started:
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except BodyTooLarge:
            pass

        if too_large and not response_started:
            await _send_413(send)
