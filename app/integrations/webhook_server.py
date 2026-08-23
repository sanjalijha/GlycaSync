"""Run the inbound WhatsApp webhook beside the console.

Streamlit cannot accept Twilio POSTs. Starting uvicorn in-process means
`streamlit run ui/app.py` is enough for local inbound, once a public HTTPS
tunnel points at this listener.
"""

from __future__ import annotations

import logging
import socket
import threading
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_running = False
_error: Optional[str] = None
_port = 8000


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def listener_status() -> dict:
    settings = get_settings()
    reachable = _port_open("127.0.0.1", _port)
    return {
        "running": _running or reachable,
        "port": _port,
        "error": _error,
        "webhook_url": settings.webhook_url,
        "public": not settings.webhook_url.startswith("http://localhost"),
    }


def ensure_webhook_running(*, host: str = "0.0.0.0", port: int = 8000) -> dict:
    """Start the FastAPI listener once. A bound port is treated as already up."""
    global _running, _error, _port
    _port = port
    with _lock:
        if _running:
            return listener_status()
        if _port_open("127.0.0.1", port):
            _running = True
            _error = None
            return listener_status()
        try:
            import uvicorn

            from app.main import app

            config = uvicorn.Config(app, host=host, port=port, log_level="warning")
            server = uvicorn.Server(config)
            thread = threading.Thread(target=server.run, daemon=True, name="glycasync-webhook")
            thread.start()
            _running = True
            _error = None
        except Exception as exc:  # noqa: BLE001
            _error = str(exc)
            logger.warning("Could not start the WhatsApp webhook listener: %s", exc)
    return listener_status()
