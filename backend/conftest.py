"""
Pytest hook to avoid spurious stdout/stderr flush crashes on Windows runners.

Windows can raise OSError(22, "Invalid argument") when pytest flushes stdio at
teardown. Wrap stdio to ignore only that specific case and re-raise others.
"""
import errno
import os
import sys
from typing import Any


def _wrap_stream(stream):
    class _SafeStream:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def write(self, data: str) -> Any:  # pragma: no cover - passthrough
            return self._wrapped.write(data)

        def flush(self) -> None:
            try:
                self._wrapped.flush()
            except OSError as exc:
                if os.name == "nt" and exc.errno == errno.EINVAL:
                    return
                raise

        def __getattr__(self, item: str) -> Any:
            return getattr(self._wrapped, item)

    return _SafeStream(stream)


def _harden_windows_stdio() -> None:
    sys.stdout = _wrap_stream(sys.stdout)  # type: ignore[assignment]
    sys.__stdout__ = _wrap_stream(sys.__stdout__)  # type: ignore[assignment]
    sys.stderr = _wrap_stream(sys.stderr)  # type: ignore[assignment]
    sys.__stderr__ = _wrap_stream(sys.__stderr__)  # type: ignore[assignment]


if os.name == "nt":
    _harden_windows_stdio()

    def pytest_configure(config):  # pragma: no cover - test harness
        # Pytest replaces stdio during capture; wrap again to keep flush safe.
        _harden_windows_stdio()

    def pytest_unconfigure(config):  # pragma: no cover - test harness
        # Ensure final flush after teardown uses the hardened streams.
        _harden_windows_stdio()
