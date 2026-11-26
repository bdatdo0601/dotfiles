"""Exercise the managed tmux configuration on an isolated server."""

import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TmuxConfigTests(unittest.TestCase):
    """Load the managed tmux.conf on an isolated server."""

    def test_shift_enter_reaches_app_as_csi_u(self):
        tmux = shutil.which("tmux")
        socket = "tmux-config-test-" + uuid.uuid4().hex
        config = ROOT / "dot_config/tmux/tmux.conf"
        temp = tempfile.TemporaryDirectory(prefix="tmux-config-test-")
        self.addCleanup(temp.cleanup)
        out = Path(temp.name) / "keys"

        def run(*args):
            return subprocess.run([tmux, "-L", socket, *args], check=True,
                                  text=True, capture_output=True, timeout=10)

        self.addCleanup(subprocess.run, [tmux, "-L", socket, "kill-server"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=10, check=False)
        # Like Claude Code: request modifyOtherKeys mode 2, then read raw keys.
        reader = (
            "import os, sys, tty\n"
            "tty.setraw(0)\n"
            "sys.stdout.write('\\x1b[>4;2m'); sys.stdout.flush()\n"
            "data = b''\n"
            "while not data.endswith(b'X'): data += os.read(0, 64)\n"
            f"open({str(out)!r}, 'wb').write(data)\n"
        )
        run("-f", str(config), "new-session", "-d", "-s", "keys",
            sys.executable, "-c", reader)
        # Poll with server round trips until tmux has processed the request.
        for _ in range(500):
            mode = run("display-message", "-p", "-t", "=keys:",
                       "#{pane_key_mode}").stdout.strip()
            if mode == "Ext 2":
                break
        self.assertEqual(mode, "Ext 2")
        run("send-keys", "-t", "=keys:", "S-Enter", "X")
        for _ in range(500):
            if out.exists() and out.read_bytes().endswith(b"X"):
                break
            run("display-message", "-p", "")
        self.assertEqual(out.read_bytes(), b"\x1b[13;2uX")


if __name__ == "__main__":
    unittest.main()
