"""Build the public URL for the worksheet web app (reverse proxy / path prefix)."""

from __future__ import annotations

from starlette.requests import Request


def worksheet_public_url(request: Request) -> str:
    """
    Infer ``scheme://host[/prefix]`` as clients see it.

    Uses ``X-Forwarded-Proto``, ``X-Forwarded-Host``, ``X-Forwarded-Prefix`` when
    present, else ``Host`` and the ASGI ``root_path`` (sub-application mount).
    Does **not** read environment variables — use ``ANALOG_CLOCK_WORKSHEET_APP_URL``
    in :func:`analog_clock_worksheet.pdf_gen._resolve_footer_app_url` to override.
    """
    xf_proto = request.headers.get("x-forwarded-proto")
    xf_host = request.headers.get("x-forwarded-host")
    xf_prefix = (request.headers.get("x-forwarded-prefix") or "").strip()

    scheme = (xf_proto or request.url.scheme or "http").split(",")[0].strip()
    host = (xf_host or request.headers.get("host") or "").split(",")[0].strip()
    if not host:
        return ""

    if xf_prefix:
        if not xf_prefix.startswith("/"):
            xf_prefix = "/" + xf_prefix
        xf_prefix = xf_prefix.rstrip("/")
    root = (request.scope.get("root_path") or "").strip().rstrip("/")
    if root and not root.startswith("/"):
        root = "/" + root
    prefix = xf_prefix or root

    base = f"{scheme}://{host}"
    if prefix:
        base += prefix
    return base.rstrip("/")
