"""
Pytest hook to avoid spurious stdout flush crashes on Windows runners.

Windows can raise OSError(22, "Invalid argument") when pytest flushes sys.stdout
at teardown. Wrap stdout to ignore only that specific case and re-raise others.
"""
import errno
import os
import sys
from typing import Any


def _wrap_stdout(stdout):
    class _SafeStdout:
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

    return _SafeStdout(stdout)


def _harden_windows_stdout() -> None:
    sys.stdout = _wrap_stdout(sys.stdout)  # type: ignore[assignment]
    # Pytest restores to sys.__stdout__ during teardown; wrap that as well.
    sys.__stdout__ = _wrap_stdout(sys.__stdout__)  # type: ignore[assignment]


if os.name == "nt":
    _harden_windows_stdout()

    def pytest_configure(config):  # pragma: no cover - test harness
        # Pytest replaces sys.stdout during capture; wrap again to keep flush safe.
        _harden_windows_stdout()

    def pytest_unconfigure(config):  # pragma: no cover - test harness
        # Ensure final flush after teardown uses the hardened stream.
        _harden_windows_stdout()
