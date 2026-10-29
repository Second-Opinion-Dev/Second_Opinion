"""One progress line on stderr, shared by the long-running scripts.

On a terminal the line is redrawn in place; anywhere else (a log file, a pipe) a plain line is
written every LINE_INTERVAL seconds, so logs show progress without one line per update.
When the pipeline driver names a file in PROGRESS_FILE_ENV, the latest state is also written
there as JSON, so the driver can show it in its status line.
"""
from contextlib import contextmanager
import json
import os
import shutil
import sys
import threading
import time

# Seconds between plain progress lines when the output is not a terminal.
LINE_INTERVAL = 30
# Seconds between redraws on a terminal.
REDRAW_INTERVAL = 0.2
# Environment variable naming the JSON file a stage reports its progress to.
PROGRESS_FILE_ENV = 'SECOND_OPINION_PROGRESS_FILE'
# Seconds between writes of that file.
REPORT_INTERVAL = 0.5


def duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{seconds // 60}m {seconds % 60:02d}s'
    return f'{seconds // 3600}h {seconds % 3600 // 60:02d}m'


def bar_line(label: str, share: float, amount: str, elapsed: float, width: int = 100, estimate: bool = True) -> str:
    """'<label> [####----] 42.0%  <amount>, <elapsed> elapsed, ~<left> left', at most `width` characters.

    Leave out the time left (`estimate=False`) when the share does not grow evenly with time."""
    share = min(max(share, 0.0), 1.0)
    left = f', ~{duration(elapsed * (1 - share) / share)} left' if estimate and share > 0 else ''
    text = f' {share:6.1%}  {amount}, {duration(elapsed)} elapsed{left}'
    bar = max(10, min(30, width - len(f'{label} [] ') - len(text)))
    filled = int(bar * share)
    return f"{label} [{'#' * filled}{'-' * (bar - filled)}]{text}"[:width]


class Progress:
    def __init__(self, stream=None, interactive: bool | None = None, enabled: bool = True):
        """With `enabled=False` nothing is drawn or reported, and `message` just prints."""
        self.stream = stream or sys.stderr
        self.interactive = self.stream.isatty() if interactive is None else interactive
        self.enabled = enabled
        self.started = time.monotonic()
        self.shown, self.drawn, self.written, self.line = 0, 0.0, time.monotonic(), ''
        self.share, self.reported = None, 0.0
        self.report_path = os.environ.get(PROGRESS_FILE_ENV) if enabled else None
        # Messages can come from other threads (the pipeline driver's stages) while the line is drawn.
        self.lock = threading.RLock()

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
        self.show(bar_line(label, share, amount, self.elapsed(), self.width()), share=share)

    def step(self, label: str, index: int, count: int, within: float, detail: str) -> None:
        """Progress through `count` numbered steps: step `index` (from 0) is `within` (0 to 1) done.

        The steps are not equally long, so the share is a rough guide and no time left is shown."""
        share = (index + min(max(within, 0.0), 1.0)) / count
        self.show(bar_line(label, share, f'step {index + 1}/{count}: {detail}', self.elapsed(), self.width(),
                           estimate=False), share=share)

    def show(self, line: str, force: bool = False, share: float | None = None) -> None:
        """Make `line` the current progress; it is drawn now or at the next allowed moment.

        `share` is the fraction done, or None when it is not known (for example in a phase)."""
        if not self.enabled:
            return
        with self.lock:
            self.line, self.share = line[:self.width()], share
            self._report(force)
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
            first = True
            while True:
                # The step's first line is written at once everywhere; after that it is forced only on a
                # terminal, so the seconds visibly count there while logs keep their usual interval.
                self.show(f'{text} ... {duration(time.monotonic() - started)} elapsed', force=first or self.interactive)
                first = False
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
        with self.lock:
            if self.enabled and self.interactive and self.shown:
                self.stream.write('\r' + ' ' * self.shown + '\r')
                self.stream.flush()
                self.shown = 0
            out = stream or sys.stdout
            out.write(text + '\n')
            out.flush()
            if self.enabled and self.interactive and self.line:
                self._draw()

    def close(self, line: str | None = None) -> None:
        """Draw the last state and end the line."""
        if not self.enabled:
            return
        with self.lock:
            if line is not None:
                self.line = line[:self.width()]
            self._report(force=True)
            if self.interactive:
                self._draw()
                self.stream.write('\n')
                self.stream.flush()
            elif self.line:
                self.stream.write(self.line + '\n')
                self.stream.flush()
            self.shown = 0

    def _report(self, force: bool) -> None:
        now = time.monotonic()
        if not self.report_path or (not force and now - self.reported < REPORT_INTERVAL):
            return
        self.reported = now
        temporary = f'{self.report_path}.tmp'
        try:
            with open(temporary, 'w', encoding='utf-8') as stream:
                json.dump({'share': self.share, 'text': self.line}, stream)
            os.replace(temporary, self.report_path)
        except OSError:
            pass  # a reader holds the file (Windows); the next report replaces it

    def _draw(self) -> None:
        # Pad over the previous line, which can be longer than this one.
        self.stream.write('\r' + self.line.ljust(self.shown))
        self.stream.flush()
        self.shown = len(self.line)
