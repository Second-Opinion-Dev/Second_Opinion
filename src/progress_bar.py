"""One progress line on stderr, shared by the long-running scripts.

On a terminal the line is redrawn in place; anywhere else (a log file, a pipe) a plain line is
written every LINE_INTERVAL seconds, so logs show progress without one line per update.
"""
from contextlib import contextmanager
import os
import shutil
import sys
import threading
import time

# Seconds between plain progress lines when the output is not a terminal.
LINE_INTERVAL = 30
# Seconds between redraws on a terminal.
REDRAW_INTERVAL = 0.2


def duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{seconds // 60}m {seconds % 60:02d}s'
    return f'{seconds // 3600}h {seconds % 3600 // 60:02d}m'


def bar_line(label: str, share: float, amount: str, elapsed: float, width: int = 100) -> str:
    """'<label> [####----] 42.0%  <amount>, <elapsed> elapsed, ~<left> left', at most `width` characters."""
    share = min(max(share, 0.0), 1.0)
    left = f', ~{duration(elapsed * (1 - share) / share)} left' if share > 0 else ''
    text = f' {share:6.1%}  {amount}, {duration(elapsed)} elapsed{left}'
    bar = max(10, min(30, width - len(f'{label} [] ') - len(text)))
    filled = int(bar * share)
    return f"{label} [{'#' * filled}{'-' * (bar - filled)}]{text}"[:width]


class Progress:
    def __init__(self, stream=None, interactive: bool | None = None):
        self.stream = stream or sys.stderr
        self.interactive = self.stream.isatty() if interactive is None else interactive
        self.started = time.monotonic()
        self.shown, self.drawn, self.written, self.line = 0, 0.0, time.monotonic(), ''

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def width(self) -> int:
        if not self.interactive:
            return 100
        try:
            return os.get_terminal_size(self.stream.fileno()).columns - 1
        except (AttributeError, OSError, ValueError):
            return shutil.get_terminal_size().columns - 1

    def bar(self, label: str, share: float, amount: str) -> None:
        self.show(bar_line(label, share, amount, self.elapsed(), self.width()))

    def show(self, line: str, force: bool = False) -> None:
        """Make `line` the current progress; it is drawn now or at the next allowed moment."""
        self.line = line[:self.width()]
        now = time.monotonic()
        if self.interactive and (force or now - self.drawn >= REDRAW_INTERVAL):
            self._draw()
            self.drawn = now
        elif not self.interactive and (force or now - self.written >= LINE_INTERVAL):
            self.stream.write(self.line + '\n')
            self.stream.flush()
            self.written = now

    @contextmanager
    def phase(self, text: str):
        """Show `text` with a ticking elapsed time while a step that reports no progress of its own runs."""
        started, stop = time.monotonic(), threading.Event()

        def tick():
            while True:
                # Forced on a terminal so the seconds visibly count; elsewhere the usual interval applies.
                self.show(f'{text} ... {duration(time.monotonic() - started)} elapsed', force=self.interactive)
                if stop.wait(1):
                    return

        ticker = threading.Thread(target=tick, daemon=True)
        ticker.start()
        try:
            yield
        finally:
            stop.set()
            ticker.join()

    def message(self, text: str, stream=None) -> None:
        """Print a line of ordinary output without breaking the progress line."""
        if self.interactive and self.shown:
            self.stream.write('\r' + ' ' * self.shown + '\r')
            self.stream.flush()
            self.shown = 0
        out = stream or sys.stdout
        out.write(text + '\n')
        out.flush()
        if self.interactive and self.line:
            self._draw()

    def close(self, line: str | None = None) -> None:
        """Draw the last state and end the line."""
        if line is not None:
            self.line = line[:self.width()]
        if self.interactive:
            self._draw()
            self.stream.write('\n')
            self.stream.flush()
        elif self.line:
            self.stream.write(self.line + '\n')
            self.stream.flush()
        self.shown = 0

    def _draw(self) -> None:
        # Pad over the previous line, which can be longer than this one.
        self.stream.write('\r' + self.line.ljust(self.shown))
        self.stream.flush()
        self.shown = len(self.line)
