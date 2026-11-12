"""Exercise the helper with real tmux and a fake Claude; no model calls."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "dot_customscripts/executable_claude-session"


class ClaudeSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="claude-session-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.socket = "claude-session-test-" + uuid.uuid4().hex
        self.tmux = shutil.which("tmux")
        self.addCleanup(self.stop_server)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.record = self.base / "record.json"
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}")
        self.env.pop("TMUX", None)
        self.env.pop("TMUX_PANE", None)
        # Isolate tests from all user sessions and tmux plugins. Record attach
        # requests instead of requiring an interactive test-runner terminal.
        self.write_executable("tmux", f'''#!/bin/bash
case "$1" in
  attach-session|switch-client)
    printf '%s\\n' "$@" > {shlex.quote(str(self.base / 'attach'))}
    exit 0 ;;
esac
exec {shlex.quote(self.tmux)} -L {self.socket} -f /dev/null "$@"
''')
        self.write_executable("claude", f'''#!{sys.executable}
import json, os, subprocess, sys
from pathlib import Path
Path({str(self.record)!r}).write_text(json.dumps({{
    "cwd": os.getcwd(), "args": sys.argv[1:], "tty": os.isatty(0)
}}))
subprocess.run(["tmux", "wait-for", "-S", "ready"], check=True)
subprocess.run(["tmux", "wait-for", "release"], check=True)
''')

    def write_executable(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def stop_server(self):
        subprocess.run([self.tmux, "-L", self.socket, "kill-server"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=10, check=False)

    def run_helper(self, *args, success=True, env=None):
        result = subprocess.run(["bash", str(HELPER), *args], cwd=ROOT,
                                env=env or self.env, text=True,
                                capture_output=True, timeout=10)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def start(self, name="example", directory=None):
        directory = directory or self.base
        result = self.run_helper("start", name, str(directory))
        # Completion handshake, not a sleep or elapsed-time assertion.
        subprocess.run([str(self.bin / "tmux"), "wait-for", "ready"],
                       env=self.env, check=True, timeout=10)
        return result

    def test_launch_exact_arguments_directory_and_terminal(self):
        directory = self.base / "space ' quote; $(touch INJECTED)"
        directory.mkdir()
        self.start("iron-fillet", directory)
        self.assertEqual(json.loads(self.record.read_text()), {
            "cwd": str(directory),
            "args": ["--dangerously-skip-permissions", "--remote-control", "iron-fillet"],
            "tty": True,
        })
        self.assertFalse((ROOT / "INJECTED").exists())
        self.assertEqual(self.run_helper("list").stdout.strip(), "iron-fillet")

    def test_duplicate_does_not_replace_session(self):
        self.start()
        result = self.run_helper("start", "example", str(self.base), success=False)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.run_helper("list").stdout.strip(), "example")

    def test_noninteractive_ssh_path(self):
        local_bin = self.base / ".local/bin"
        local_bin.mkdir(parents=True)
        (self.bin / "claude").rename(local_bin / "claude")
        self.env.update(HOME=str(self.base), PATH=f"{self.bin}:/usr/bin:/bin")
        self.start()
        self.assertEqual(json.loads(self.record.read_text())["args"],
                         ["--dangerously-skip-permissions", "--remote-control", "example"])

    def test_attach_requires_exact_name(self):
        self.start("example-long")
        self.run_helper("attach", "example", success=False)
        self.run_helper("attach", "example-long")
        self.assertEqual((self.base / "attach").read_text(),
                         "attach-session\n-t\n=claude-example-long\n")

    def test_attach_inside_tmux_switches_client(self):
        self.start()
        env = dict(self.env, TMUX="existing-client")
        self.run_helper("attach", "example", env=env)
        self.assertEqual((self.base / "attach").read_text(),
                         "switch-client\n-t\n=claude-example\n")

    def test_empty_list_and_unrelated_sessions(self):
        self.assertIn("No Claude sessions", self.run_helper().stdout)
        subprocess.run([str(self.bin / "tmux"), "new-session", "-d", "-s",
                        "unrelated", "tmux", "wait-for", "release"],
                       env=self.env, check=True, timeout=10)
        self.assertIn("No Claude sessions", self.run_helper("list").stdout)

    def test_invalid_inputs(self):
        for name in ("", "-option", "bad.name", "bad:name", "a b", "$(touch INJECTED)"):
            with self.subTest(name=name):
                self.run_helper("start", name, str(self.base), success=False)
        self.run_helper("start", "valid", str(self.base / "missing"), success=False)
        self.run_helper("attach", "missing", success=False)
        for args in (("start",), ("attach",), ("list", "extra"), ("unknown",)):
            self.run_helper(*args, success=False)
        self.assertIn("Usage:", self.run_helper("--help").stdout)


class TmuxConfigTests(unittest.TestCase):
    """Load the managed tmux.conf on an isolated server."""

    def test_shift_enter_reaches_app_as_csi_u(self):
        tmux = shutil.which("tmux")
        socket = "claude-session-test-" + uuid.uuid4().hex
        config = ROOT / "dot_config/tmux/tmux.conf"
        temp = tempfile.TemporaryDirectory(prefix="claude-session-test-")
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
