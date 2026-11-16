"""The entrance's report read past the window line every named stage prints first.

Design: lib/DESIGN.md#a-runs-window-and-the-entrances-cap
"""
WINDOW = "work: window "


def past_window(text):
    """Standard output without its window lines, so the report parses as one document."""
    if isinstance(text, bytes):
        return past_window(text.decode("utf-8")).encode("utf-8")
    return "".join(line for line in text.splitlines(keepends=True) if not line.startswith(WINDOW))


class PastWindow:
    """`capsys` for a test that reads the report, not the window line before it."""

    def __init__(self, capture):
        self._capture = capture

    def readouterr(self):
        result = self._capture.readouterr()
        return type(result)(past_window(result.out), result.err)

    def __getattr__(self, name):
        return getattr(self._capture, name)
