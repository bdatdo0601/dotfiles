"""Exercise the helper with real tmux and a fake Claude; no model calls."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

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
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        XDG_STATE_HOME=str(self.base / "state"))
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
import json, os, signal, subprocess, sys, uuid
from pathlib import Path
args = sys.argv[1:]
name = args[args.index("--remote-control") + 1]
session_id = args[args.index("--resume") + 1] if "--resume" in args else str(uuid.uuid4())
transcript = Path({str(self.base)!r}) / (session_id + ".jsonl")
if "--resume" in args and (not transcript.exists() or os.environ.get("FAKE_RESUME_FAIL")):
    sys.exit(1)
transcript.touch()
settings = json.loads(args[args.index("--settings") + 1])
hook = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
subprocess.run(hook, shell=True, check=True, input=json.dumps({{
    "session_id": session_id, "cwd": os.getcwd(), "transcript_path": str(transcript)
}}), text=True)
record = {{"cwd": os.getcwd(), "args": args, "tty": os.isatty(0),
           "id": session_id, "pid": os.getpid()}}
Path({str(self.record)!r}).write_text(json.dumps(record))
(Path({str(self.base)!r}) / (name + ".json")).write_text(json.dumps(record))
def stop(*_):
    if (Path({str(self.base)!r}) / "hold-stop").exists():
        subprocess.run(["tmux", "wait-for", "-S", "stopping"], check=True)
        subprocess.run(["tmux", "wait-for", "stop-release"], check=True)
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
subprocess.run(["tmux", "wait-for", "-S", "ready-" + name], check=True)
while True:
    signal.pause()
''')
        self.write_executable("brew", f'''#!{sys.executable}
import json, os, signal, subprocess, sys
from pathlib import Path
panes = subprocess.check_output(["tmux", "list-panes", "-a", "-F",
    "#{{session_name}} #{{pane_id}} #{{pane_dead}}"], text=True).splitlines() if Path({str(self.record)!r}).exists() else []
Path({str(self.base / 'brew.json')!r}).write_text(json.dumps({{"args": sys.argv[1:], "panes": panes}}))
replacement = Path({str(self.bin / 'claude-new')!r})
if replacement.exists():
    replacement.replace({str(self.bin / 'claude')!r})
if os.environ.get("FAKE_BREW_INTERRUPT"):
    os.kill(os.getppid(), signal.SIGTERM)
sys.exit(int(os.environ.get("FAKE_BREW_STATUS", "0")))
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
        result = subprocess.run(["bash", str(HELPER), *args], cwd=ROOT, check=False,
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
        self.wait_ready(name)
        return result

    def wait_ready(self, name="example"):
        subprocess.run([str(self.bin / "tmux"), "wait-for", "ready-" + name],
                       env=self.env, check=True, timeout=10)

    def tmux_run(self, *args):
        return subprocess.run([str(self.bin / "tmux"), *args], env=self.env,
                              text=True, capture_output=True, check=True, timeout=10).stdout.strip()

    def record_for(self, name="example"):
        return json.loads((self.base / (name + ".json")).read_text())

    def pane_for(self, name="example"):
        return self.tmux_run("list-panes", "-t", "=claude-" + name, "-F", "#{pane_id}")

    def launch_args(self, record):
        args = record["args"].copy()
        settings_index = args.index("--settings")
        del args[settings_index:settings_index + 2]
        return args

    def test_launch_exact_arguments_directory_and_terminal(self):
        directory = self.base / "space ' quote; $(touch INJECTED)"
        directory.mkdir()
        self.start("iron-fillet", directory)
        record = self.record_for("iron-fillet")
        self.assertEqual(record["cwd"], str(directory))
        self.assertEqual(self.launch_args(record),
                         ["--dangerously-skip-permissions", "--remote-control", "iron-fillet"])
        self.assertTrue(record["tty"])
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
        self.assertEqual(self.launch_args(self.record_for()),
                         ["--dangerously-skip-permissions", "--remote-control", "example"])

    def test_upgrade_stops_all_then_resumes_exact_conversations_in_same_panes(self):
        directory = self.base / "space ' quote; $(touch INJECTED)"
        directory.mkdir()
        self.start("first", directory)
        self.start("second", directory)
        before = {name: self.record_for(name) for name in ("first", "second")}
        panes = {name: self.pane_for(name) for name in before}
        # A shell pane in a Claude session and an unrelated session stay alive.
        extra = self.tmux_run("split-window", "-d", "-P", "-F", "#{pane_id}",
                              "-t", "=claude-first:", "tmux", "wait-for", "release")
        self.tmux_run("new-session", "-d", "-s", "unrelated", "tmux", "wait-for", "release")
        self.tmux_run("set-option", "-p", "-t", panes["second"], "remain-on-exit", "failed")
        # Keep a real attached tmux control client through both restarts.
        log = (self.base / "client.log").open("w")
        self.addCleanup(log.close)
        client = subprocess.Popen([self.tmux, "-L", self.socket, "-C", "attach-session",
                                   "-t", "=claude-first"], env=self.env, text=True,
                                  stdin=subprocess.PIPE, stdout=log, stderr=log)
        self.addCleanup(client.communicate, "detach-client\n", timeout=10)
        client.stdin.write("wait-for -S attached\n")
        client.stdin.flush()
        self.tmux_run("wait-for", "attached")
        for _ in range(2):
            result = self.run_helper("upgrade")
            self.assertIn("Resumed first", result.stdout)
            self.assertIn("Resumed second", result.stdout)
            for name, original in before.items():
                self.wait_ready(name)
                after = self.record_for(name)
                self.assertEqual(after["id"], original["id"])
                self.assertNotEqual(after["pid"], original["pid"])
                self.assertEqual(after["cwd"], str(directory))
                self.assertTrue(after["tty"])
                self.assertEqual(self.pane_for(name), panes[name] if name == "second" else panes[name] + "\n" + extra)
                self.assertEqual(self.launch_args(after), ["--dangerously-skip-permissions",
                    "--remote-control", name, "--resume", original["id"]])
            self.assertIsNone(client.poll(), "Attached tmux client disconnected during upgrade")
            brew = json.loads((self.base / "brew.json").read_text())
            self.assertEqual(brew["args"], ["upgrade", "claude-code@latest"])
            for row in brew["panes"]:
                session, pane, dead = row.split()
                self.assertEqual(dead, "1" if pane in panes.values() else "0", session)
            self.assertEqual(self.tmux_run("display-message", "-p", "-t", panes["first"],
                                          "#{remain-on-exit}"), "off")
            self.assertEqual(self.tmux_run("display-message", "-p", "-t", panes["second"],
                                          "#{remain-on-exit}"), "failed")
        self.assertFalse((ROOT / "INJECTED").exists())

    def test_upgrade_failure_and_interruption_restore_sessions(self):
        self.start()
        original = self.record_for()
        for failure in ({"FAKE_BREW_STATUS": "23"}, {"FAKE_BREW_INTERRUPT": "1"}):
            with self.subTest(failure=failure):
                result = self.run_helper("upgrade", env=dict(self.env, **failure), success=False)
                self.assertEqual(result.returncode, 23 if "FAKE_BREW_STATUS" in failure else 143)
                self.wait_ready()
                self.assertEqual(self.record_for()["id"], original["id"])
                self.assertNotEqual(self.record_for()["pid"], original["pid"])
                self.assertFalse((self.base / "state/claude-session/upgrade.lock").exists())

    def test_upgrade_preflights_all_sessions_before_stopping_any(self):
        self.start("first")
        original = self.record_for("first")
        self.tmux_run("new-session", "-d", "-s", "claude-old", "tmux", "wait-for", "release")
        result = self.run_helper("upgrade", success=False)
        self.assertIn("restart it with the updated", result.stderr)
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", "=claude-first:",
                                      "#{pane_pid}"), str(original["pid"]))
        self.assertFalse((self.base / "brew.json").exists())

    def test_upgrade_requires_saved_conversation(self):
        self.start()
        original = self.record_for()
        (self.base / (original["id"] + ".jsonl")).unlink()
        result = self.run_helper("upgrade", success=False)
        self.assertIn("Send a message", result.stderr)
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", self.pane_for(),
                                      "#{pane_pid}"), str(original["pid"]))
        self.assertFalse((self.base / "brew.json").exists())

    def test_upgrade_cannot_stop_its_own_pane(self):
        self.start()
        result = self.run_helper("upgrade", env=dict(self.env, TMUX_PANE=self.pane_for()), success=False)
        self.assertIn("separate terminal", result.stderr)
        self.assertFalse((self.base / "brew.json").exists())

    def test_resume_existing_conversation_enables_upgrades(self):
        session_id = str(uuid.uuid4())
        (self.base / (session_id + ".jsonl")).touch()
        self.run_helper("resume", "example", str(self.base), session_id)
        self.wait_ready()
        self.assertEqual(self.record_for()["id"], session_id)
        self.run_helper("upgrade")
        self.wait_ready()
        self.assertEqual(self.record_for()["id"], session_id)

    def test_failed_resume_preserves_pane_and_metadata_for_retry(self):
        self.start()
        original = self.record_for()
        pane = self.pane_for()
        self.tmux_run("set-environment", "-g", "FAKE_RESUME_FAIL", "1")
        result = self.run_helper("upgrade", success=False)
        self.assertIn("did not finish resuming", result.stderr)
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", pane, "#{pane_dead}"), "1")
        self.assertEqual(json.loads(self.tmux_run("show-options", "-pv", "-t", pane,
                                                 "@claude_session"))["id"], original["id"])
        self.tmux_run("set-environment", "-gu", "FAKE_RESUME_FAIL")
        self.run_helper("upgrade")
        self.wait_ready()
        self.assertEqual(self.record_for()["id"], original["id"])
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", pane, "#{remain-on-exit}"), "off")

    def test_interruption_during_shutdown_still_restores_session(self):
        self.start()
        original = self.record_for()
        (self.base / "hold-stop").touch()
        process = subprocess.Popen(["bash", str(HELPER), "upgrade"], cwd=ROOT, env=self.env,
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(process.kill)
        self.tmux_run("wait-for", "stopping")
        process.terminate()
        self.tmux_run("wait-for", "-S", "stop-release")
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 143, stdout + stderr)
        self.wait_ready()
        self.assertEqual(self.record_for()["id"], original["id"])
        self.assertFalse((self.base / "brew.json").exists())

    def test_upgrade_lock_blocks_other_upgrades_and_new_sessions(self):
        self.start()
        original = self.record_for()
        (self.base / "state/claude-session/upgrade.lock").mkdir(parents=True)
        self.assertIn("Another upgrade", self.run_helper("upgrade", success=False).stderr)
        self.assertIn("upgrade is running", self.run_helper("start", "second", str(self.base),
                                                          success=False).stderr)
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", self.pane_for(),
                                      "#{pane_pid}"), str(original["pid"]))
        self.assertFalse((self.base / "brew.json").exists())

    def test_stale_tracking_does_not_stop_a_replacement_process(self):
        self.start()
        pane = self.pane_for()
        state = json.loads(self.tmux_run("show-options", "-pv", "-t", pane, "@claude_session"))
        state["pid"] = "0"
        self.tmux_run("set-option", "-p", "-t", pane, "@claude_session", json.dumps(state))
        self.assertIn("tracking is not ready", self.run_helper("upgrade", success=False).stderr)
        self.assertFalse((self.base / "brew.json").exists())

    def test_upgrade_without_sessions(self):
        self.run_helper("upgrade")
        self.assertEqual(json.loads((self.base / "brew.json").read_text())["args"],
                         ["upgrade", "claude-code@latest"])

    def test_upgrade_resolves_replacement_executable(self):
        self.start()
        original = self.record_for()
        # Replace the old executable during brew; resuming must use the new one.
        (self.bin / "claude").rename(self.bin / "claude-new")
        self.write_executable("claude", "#!/bin/sh\nexit 99\n")
        self.run_helper("upgrade")
        self.wait_ready()
        self.assertEqual(self.record_for()["id"], original["id"])

    def test_tracking_follows_clear_or_resume_in_same_process(self):
        self.start()
        record = self.record_for()
        settings = json.loads(record["args"][record["args"].index("--settings") + 1])
        hook = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        new_id = str(uuid.uuid4())
        transcript = self.base / (new_id + ".jsonl")
        transcript.touch()
        subprocess.run(hook, shell=True, check=True, text=True, timeout=10,
                       env=dict(self.env, TMUX_PANE=self.pane_for()), input=json.dumps({
                           "session_id": new_id, "cwd": str(self.base), "transcript_path": str(transcript)}))
        self.run_helper("upgrade")
        self.wait_ready()
        self.assertEqual(self.record_for()["id"], new_id)

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
        self.run_helper("resume", "valid", str(self.base), "not-a-uuid", success=False)
        self.run_helper("attach", "missing", success=False)
        for args in (("start",), ("resume",), ("attach",), ("list", "extra"),
                     ("upgrade", "extra"), ("unknown",)):
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
