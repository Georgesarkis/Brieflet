"""Notifier: runs the config's notify_cmd (geolinux: ntfy push) if it exists; silent otherwise."""
from __future__ import annotations

import shutil
import subprocess


class CommandNotifier:
    def __init__(self, cmd: str | None):
        self.cmd = cmd if cmd and shutil.which(cmd) else None

    def send(self, msg: str) -> None:
        if self.cmd:
            subprocess.run([self.cmd, msg[:300]], check=False, timeout=30)
