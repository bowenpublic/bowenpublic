"""
conftest.py — shared fixtures for the Bowen retrieval/contract harness.

Design constraints (see tests/SWARM-CHARTER.md):
  * `backend.app.main` is imported WITHOUT running its startup event. The index
    is loaded here from EMBEDDINGS_DIR and assigned onto the module globals.
  * No test may reach api.anthropic.com or any other remote host. The Anthropic
    client is a stub sentinel and outbound sockets are blocked outright.
  * The sentence-transformers model is loaded from the local HF cache in
    offline mode.
"""

import json
import os
import socket
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_FIXTURE = REPO_ROOT / "backend" / "tests" / "fixtures" / "mini"

# --- Environment must be settled BEFORE backend.app.main is imported ---------
# `setdefault` so the acceptance command's own values win.
os.environ.setdefault("EMBEDDINGS_DIR", str(DEFAULT_FIXTURE))
os.environ.setdefault("BOWEN_STUB_LLM", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "")  # load_dotenv() will not override
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("LOGS_DIR", tempfile.mkdtemp(prefix="bowen-test-logs-"))
os.environ.setdefault("DEBUG", "false")

if os.environ.get("BOWEN_STUB_LLM", "").strip().lower() not in ("1", "true", "yes", "on"):
    raise RuntimeError(
        "BOWEN_STUB_LLM must be enabled for the test suite — refusing to run "
        "against the real Anthropic API."
    )

GOLDEN_PATH = Path(__file__).parent / "golden" / "retrieval.json"


# --- Network kill-switch -----------------------------------------------------

_ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost"}
_real_connect = socket.socket.connect
_real_create_connection = socket.create_connection


class NetworkBlockedError(RuntimeError):
    """Raised when a test tries to open a non-local socket."""


def _guarded_connect(self, address, *args, **kwargs):
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, str) and host in _ALLOWED_HOSTS:
        return _real_connect(self, address, *args, **kwargs)
    raise NetworkBlockedError(f"Outbound network access is blocked in tests: {address!r}")


def _guarded_create_connection(address, *args, **kwargs):
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, str) and host in _ALLOWED_HOSTS:
        return _real_create_connection(address, *args, **kwargs)
    raise NetworkBlockedError(f"Outbound network access is blocked in tests: {address!r}")


@pytest.fixture(scope="session", autouse=True)
def block_network():
    socket.socket.connect = _guarded_connect
    socket.create_connection = _guarded_create_connection
    try:
        yield
    finally:
        socket.socket.connect = _real_connect
        socket.create_connection = _real_create_connection


# --- The application module, loaded but not "started" ------------------------

@pytest.fixture(scope="session")
def app_module(block_network):
    """Import backend.app.main and hand-load the index (no startup event)."""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    from backend.app import main as main_module

    embeddings_dir = Path(os.environ["EMBEDDINGS_DIR"])
    if not embeddings_dir.is_absolute():
        embeddings_dir = REPO_ROOT / embeddings_dir

    embeddings_path = embeddings_dir / "embeddings.npy"
    metadata_path = embeddings_dir / "metadata.json"
    if not embeddings_path.exists() or not metadata_path.exists():
        pytest.skip(
            f"Fixture index missing at {embeddings_dir}. Build it with "
            "backend/tests/scripts/build_fixture.py (see backend/tests/README.md)."
        )

    loaded_embeddings = np.load(embeddings_path, mmap_mode="r")
    with open(metadata_path, "r", encoding="utf-8") as fh:
        loaded_metadata = json.load(fh)
    # Same filter as startup(): wholly repealed Acts never reach search.
    (main_module.embeddings, main_module.metadata,
     _dropped) = main_module.drop_repealed_rows(loaded_embeddings, loaded_metadata)
    main_module.embedding_model = SentenceTransformer(main_module.EMBEDDING_MODEL)

    # Never a real client, whatever the ambient environment holds.
    main_module.anthropic_client = main_module.STUB_CLIENT
    assert main_module.STUB_LLM, "BOWEN_STUB_LLM must be on"

    return main_module


class SyncASGIClient:
    """A minimal synchronous client over httpx's in-process ASGI transport.

    starlette 0.35.1's TestClient passes `app=` to httpx.Client, which httpx
    0.28 removed, so TestClient cannot be constructed in this venv. ASGITransport
    also suits the harness better: it never runs the lifespan, so the app's
    startup() (which loads the full 2 GB index and builds a real Anthropic
    client) is guaranteed not to fire.
    """

    def __init__(self, app, base_url="http://testserver"):
        import asyncio
        import httpx

        self._httpx = httpx
        self._app = app
        self._base_url = base_url
        self._loop = asyncio.new_event_loop()

    def request(self, method, url, **kwargs):
        async def _go():
            transport = self._httpx.ASGITransport(app=self._app)
            async with self._httpx.AsyncClient(transport=transport,
                                               base_url=self._base_url) as ac:
                return await ac.request(method, url, **kwargs)
        return self._loop.run_until_complete(_go())

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def close(self):
        self._loop.close()


@pytest.fixture(scope="session")
def client(app_module):
    """In-process HTTP client that never runs the app's startup event."""
    c = SyncASGIClient(app_module.app)
    try:
        yield c
    finally:
        c.close()


@pytest.fixture(autouse=True)
def clean_history(app_module):
    """Conversation history is process-global; keep tests independent."""
    app_module.conversation_history.clear()
    yield
    app_module.conversation_history.clear()


@pytest.fixture(scope="session")
def golden():
    """The golden retrieval set (header + entries)."""
    with open(GOLDEN_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def golden_entries(golden):
    return golden["entries"]


@pytest.fixture(scope="session")
def fixture_acts(app_module):
    return {row["act_title"] for row in app_module.metadata}
