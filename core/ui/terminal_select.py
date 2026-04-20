"""Interactive terminal select (single or multi) using raw tty mode — no TUI deps."""

from __future__ import annotations

import sys
import termios
import tty
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class SelectOption:
    label: str
    value: Any
    selected: bool = False


@dataclass
class SelectConfig:
    title: str
    multi_select: bool = False
    highlight_color: str = "\033[46m\033[30m"  # cyan background, black text
    reset_color: str = "\033[0m"


class TerminalSelectCancelled(Exception):
    """Raised when the user presses q or Ctrl+C."""


def _writeln(text: str = "") -> None:
    """Write one logical line; use CRLF so column resets when stdin is in raw mode."""
    sys.stdout.write(text + "\r\n")


def _read_action(fd: int) -> str:
    """Read one logical key action: up, down, enter, space, done, cancel, unknown."""
    buf = sys.stdin.buffer
    b = buf.read(1)
    if not b:
        return "unknown"
    if b == b"\x03":  # Ctrl+C
        raise TerminalSelectCancelled()
    if b in (b"q", b"Q"):
        raise TerminalSelectCancelled()
    if b == b"\r" or b == b"\n":
        return "enter"
    if b == b" ":
        return "space"
    if b in (b"d", b"D"):
        return "done"
    if b == b"\x1b":
        b2 = buf.read(1)
        if b2 == b"[":
            b3 = buf.read(1)
            if b3 == b"A":
                return "up"
            if b3 == b"B":
                return "down"
        elif b2 == b"O":
            b3 = buf.read(1)
            if b3 == b"A":
                return "up"
            if b3 == b"B":
                return "down"
        return "unknown"
    return "unknown"


def _clear_and_home() -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _render(
    options: list[SelectOption],
    active: int,
    config: SelectConfig,
    footer: str,
) -> None:
    _clear_and_home()
    sys.stdout.write(config.reset_color)
    _writeln(config.title)
    _writeln()
    for i, opt in enumerate(options):
        mark = "[✓]" if opt.selected else "[ ]"
        line = f"  {mark}  {opt.label}"
        if i == active:
            _writeln(f"{config.highlight_color}{line}{config.reset_color}")
        else:
            _writeln(line)
    _writeln()
    _writeln(footer)
    sys.stdout.flush()


class TerminalSelect:
    def __init__(self, options: Sequence[SelectOption], config: SelectConfig) -> None:
        self._options = list(options)
        self._config = config
        self._active = 0

    def run(self) -> list[SelectOption]:
        if not self._options:
            return []

        fd = sys.stdin.fileno()
        if not sys.stdin.isatty():
            raise RuntimeError("Terminal select requires an interactive TTY on stdin.")

        old_settings = termios.tcgetattr(fd)
        footer_single = "↑/↓ move  Enter confirm  q quit"
        footer_multi = "↑/↓ move  Space/Enter toggle  d done  q quit"

        try:
            tty.setraw(fd)
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()

            while True:
                footer = footer_multi if self._config.multi_select else footer_single
                _render(self._options, self._active, self._config, footer)
                action = _read_action(fd)

                if action == "up":
                    self._active = (self._active - 1) % len(self._options)
                elif action == "down":
                    self._active = (self._active + 1) % len(self._options)
                elif self._config.multi_select:
                    if action == "space":
                        o = self._options[self._active]
                        o.selected = not o.selected
                    elif action == "enter":
                        o = self._options[self._active]
                        o.selected = not o.selected
                    elif action == "done":
                        return self._options
                else:
                    if action == "enter":
                        for i, o in enumerate(self._options):
                            o.selected = i == self._active
                        return self._options
        finally:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            _clear_and_home()


def terminal_select(
    options: Sequence[SelectOption],
    config: SelectConfig,
) -> list[SelectOption]:
    """Run interactive select; returns options with ``selected`` flags set."""
    return TerminalSelect(options, config).run()
