"""Exercise agy-session with real tmux, fake agy, and fake rex; no model calls."""

import fcntl
import json
import os
import pty
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "dot_customscripts/executable_agy-session"


class AgySessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agy-session-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.socket = "agy-session-test-" + uuid.uuid4().hex
        self.tmux = shutil.which("tmux")
        self.addCleanup(self.stop_server)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.record = self.base / "record.json"
        self.hooks_file = self.base / ".gemini/config/hooks.json"
        # Strip any host PATH directory containing a real `rex` binary so non-Rex
        # tests exercise tmux without touching the host Rex daemon.
        host_path = [
            p
            for p in os.environ["PATH"].split(os.pathsep)
            if p and not (Path(p) / "rex").exists()
        ]
        self.env = dict(
            os.environ,
            HOME=str(self.base),
            PATH=os.pathsep.join([str(self.bin), *host_path]),
            XDG_STATE_HOME=str(self.base / "state"),
            AGY_SESSION_RESUME_GRACE_TENTHS="3",
        )
        self.assertIsNone(shutil.which("rex", path=self.env["PATH"]))
        self.env.pop("TMUX", None)
        self.env.pop("TMUX_PANE", None)
        self.env.pop("REX_SESSION", None)
        self.env.pop("REX_BLOCK", None)
        self.env.pop("AGY_SESSION_TARGET", None)
        self.env.pop("AGY_SESSION_NAME", None)
        self.env.pop("AGY_SESSION_STATE_FILE", None)
        self.env.pop("AGY_HOOKS_FILE", None)
        # Isolate tests from all user sessions and tmux plugins. Record attach
        # requests instead of requiring an interactive test-runner terminal.
        self.write_executable(
            "tmux",
            f'''#!/bin/bash
case "$1" in
  attach-session|switch-client)
    printf '%s\\n' "$@" > {shlex.quote(str(self.base / 'attach'))}
    exit 0 ;;
esac
exec {shlex.quote(self.tmux)} -L {self.socket} -f /dev/null "$@"
''',
        )
        self.install_fake_agy("agy")
        self.install_fake_brew()

    def install_fake_agy(self, binary_name="agy", record_suffix=""):
        script = f'''#!{sys.executable}
import json, os, signal, subprocess, sys, uuid
from pathlib import Path

args = sys.argv[1:]
base = Path({str(self.base)!r})

if args == ["update"]:
    if os.environ.get("FAKE_UPDATE_RECORD", "1") == "1":
        (base / "update.json").write_text(json.dumps({{"args": args, "exe": sys.argv[0]}}))
    replacement = base / "bin/agy-new"
    if replacement.exists():
        replacement.replace(base / "bin/agy")
    if os.environ.get("FAKE_UPDATE_INTERRUPT"):
        os.kill(os.getppid(), signal.SIGTERM)
    sys.exit(int(os.environ.get("FAKE_UPDATE_STATUS", "0")))

is_resume = "--conversation" in args
session_id = args[args.index("--conversation") + 1] if is_resume else str(uuid.uuid4())
transcript = base / (session_id + ".jsonl")

if is_resume and (not transcript.exists() or os.environ.get("FAKE_RESUME_FAIL")):
    sys.exit(1)

hooks_path = Path(os.environ.get("AGY_HOOKS_FILE", str(Path.home() / ".gemini/config/hooks.json")))
hooks_data = json.loads(hooks_path.read_text()) if hooks_path.exists() else {{}}
entry = hooks_data.get("agy-session", {{}})

def run_hook(event_name, cid, tx_path):
    for handler in entry.get(event_name, []):
        res = subprocess.run(
            handler["command"],
            shell=True,
            check=True,
            text=True,
            capture_output=True,
            input=json.dumps({{
                "conversationId": cid,
                "workspacePaths": [os.getcwd()],
                "cwd": os.getcwd(),
                "transcriptPath": str(tx_path),
                "hookEventName": event_name,
            }}),
        )
        # Antigravity requires hooks to emit valid JSON on stdout.
        json.loads(res.stdout)

# Real agy does NOT fire SessionStart on idle --conversation startup unless a
# turn runs, whereas a fresh session writes a transcript and runs SessionStart.
if not is_resume and not os.environ.get("FAKE_SKIP_SESSION_START"):
    transcript.touch()
    run_hook("SessionStart", session_id, transcript)

name = os.environ.get("AGY_SESSION_NAME") or "unnamed"
record = {{
    "cwd": os.getcwd(),
    "args": args,
    "tty": os.isatty(0),
    "id": session_id,
    "pid": os.getpid(),
    "exe": os.path.basename(sys.argv[0]),
}}
Path({str(self.record)!r}).write_text(json.dumps(record))
(base / (name + {record_suffix!r} + ".json")).write_text(json.dumps(record))

def stop(*_):
    if (base / "hold-stop").exists():
        subprocess.run(["tmux", "wait-for", "-S", "stopping"], check=True)
        subprocess.run(["tmux", "wait-for", "stop-release"], check=True)
    sys.exit(0)

signal.signal(signal.SIGTERM, stop)
if os.environ.get("AGY_SESSION_TARGET") == "tmux":
    subprocess.run(["tmux", "wait-for", "-S", "ready-" + name], check=True)
else:
    (base / ("rex-ready-" + name)).write_text(str(os.getpid()))
while True:
    signal.pause()
'''
        self.write_executable(binary_name, script)

    def install_fake_brew(self, cask_installed=True):
        prefix = str(self.base)
        self.write_executable(
            "brew",
            f'''#!{sys.executable}
import json, os, signal, subprocess, sys
from pathlib import Path

args = sys.argv[1:]
if args == ["--prefix"]:
    print({prefix!r})
    sys.exit(0)
if args[:3] == ["list", "--cask", "antigravity-cli"]:
    sys.exit(0 if {cask_installed!r} else 1)

panes = subprocess.check_output(
    ["tmux", "list-panes", "-a", "-F", "#{{session_name}} #{{pane_id}} #{{pane_dead}}"],
    text=True,
).splitlines() if Path({str(self.record)!r}).exists() else []
Path({str(self.base / 'brew.json')!r}).write_text(json.dumps({{"args": args, "panes": panes}}))
replacement = Path({str(self.bin / 'agy-new')!r})
if replacement.exists():
    replacement.replace({str(self.bin / 'agy')!r})
if os.environ.get("FAKE_BREW_INTERRUPT"):
    os.kill(os.getppid(), signal.SIGTERM)
sys.exit(int(os.environ.get("FAKE_BREW_STATUS", "0")))
''',
        )

    def install_fake_rex(self):
        rex_dir = self.base / "rex-daemon"
        rex_dir.mkdir(exist_ok=True)
        (rex_dir / "sessions.json").write_text("[]")
        (rex_dir / "clients.json").write_text(json.dumps([{"client_id": "app-1", "info": {"kind": "app"}}]))
        (rex_dir / "actions.json").write_text("[]")

        def cleanup_rex():
            if not (rex_dir / "sessions.json").exists():
                return
            for sess in json.loads((rex_dir / "sessions.json").read_text()):
                pid = sess.get("pid")
                if pid:
                    try:
                        os.killpg(pid, signal.SIGTERM)
                    except OSError:
                        pass

        self.addCleanup(cleanup_rex)
        self.write_executable(
            "rex",
            f'''#!{sys.executable}
import json, os, signal, subprocess, sys, uuid
from pathlib import Path

rex_dir = Path({str(rex_dir)!r})
sessions_file = rex_dir / "sessions.json"
clients_file = rex_dir / "clients.json"
actions_file = rex_dir / "actions.json"

def load_sessions():
    return json.loads(sessions_file.read_text())

def save_sessions(data):
    sessions_file.write_text(json.dumps(data))

def load_actions():
    return json.loads(actions_file.read_text())

def save_actions(data):
    actions_file.write_text(json.dumps(data))

args = sys.argv[1:]
if args == ["ls", "--json"]:
    alive = []
    for s in load_sessions():
        try:
            os.kill(s["pid"], 0)
            alive.append(s)
        except OSError:
            pass
    save_sessions(alive)
    print(json.dumps({{"sessions": [{{"label": s["label"], "session_id": s["session_id"]}} for s in alive]}}))
    sys.exit(0)

if args == ["client", "ls", "--json"]:
    print(json.dumps({{"clients": json.loads(clients_file.read_text())}}))
    sys.exit(0)

if args and args[0] == "-C":
    client_id = args[1]
    rest = args[2:]
    actions = load_actions()
    actions.append({{"client": client_id, "args": rest}})
    save_actions(actions)
    if rest[:2] == ["do", "session.select"] and os.environ.get("FAKE_REX_SHOW_FAIL"):
        print("Error: not accepting actions")
        sys.exit(0)
    print("ok")
    sys.exit(0)

if args and args[0] == "new":
    label = args[1]
    cwd = args[args.index("-c") + 1]
    sep = args.index("--")
    cmd = args[sep + 1:]
    sid = "rex-" + uuid.uuid4().hex[:8]
    bid = "blk-" + uuid.uuid4().hex[:8]
    env = dict(os.environ, REX_SESSION=sid, REX_BLOCK=bid)
    log = open(rex_dir / (sid + ".log"), "a")
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, start_new_session=True,
                            stdin=subprocess.DEVNULL, stdout=log, stderr=log)
    sessions = load_sessions()
    sessions.append({{"label": label, "session_id": sid, "block_id": bid, "pid": proc.pid, "cwd": cwd}})
    save_sessions(sessions)
    print(json.dumps({{"session_id": sid, "initial_windows": [{{"block_ids": [bid]}}]}}))
    sys.exit(0)

if args and args[0] == "split":
    actions = load_actions()
    actions.append({{"split": args}})
    save_actions(actions)
    sys.exit(0)

if args and args[0] == "kill":
    sid = args[1]
    sessions = load_sessions()
    kept = []
    for s in sessions:
        if s["session_id"] == sid:
            try:
                os.killpg(s["pid"], signal.SIGTERM)
            except OSError:
                pass
        else:
            kept.append(s)
    save_sessions(kept)
    sys.exit(0)

sys.exit(1)
''',
        )
        return rex_dir

    def write_executable(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def stop_server(self):
        subprocess.run(
            [self.tmux, "-L", self.socket, "kill-server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )

    def run_helper(self, *args, success=True, env=None, stdin_text=None):
        result = subprocess.run(
            ["bash", str(HELPER), *args],
            cwd=ROOT,
            check=False,
            env=env or self.env,
            text=True,
            input=stdin_text,
            capture_output=True,
            timeout=15,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def start(self, name="example", directory=None, extra_args=()):
        directory = directory or self.base
        result = self.run_helper("start", name, str(directory), *extra_args)
        self.wait_ready(name)
        return result

    def wait_ready(self, name="example"):
        subprocess.run(
            [str(self.bin / "tmux"), "wait-for", "ready-" + name],
            env=self.env,
            check=True,
            timeout=10,
        )

    def wait_rex_ready(self, name="example", prev_pid=None):
        marker = self.base / ("rex-ready-" + name)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if marker.exists():
                pid = marker.read_text().strip()
                if pid and pid != str(prev_pid):
                    return int(pid)
            time.sleep(0.05)
        self.fail(f"Timed out waiting for Rex agy ready for {name}")

    def tmux_run(self, *args):
        return subprocess.run(
            [str(self.bin / "tmux"), *args],
            env=self.env,
            text=True,
            capture_output=True,
            check=True,
            timeout=10,
        ).stdout.strip()

    def record_for(self, name="example"):
        return json.loads((self.base / (name + ".json")).read_text())

    def pane_for(self, name="example"):
        return self.tmux_run("list-panes", "-t", "=agy-" + name, "-F", "#{pane_id}")

    def launch_args(self, record):
        return record["args"].copy()

    def test_launch_exact_arguments_directory_and_terminal(self):
        directory = self.base / "space ' quote; $(touch INJECTED)"
        directory.mkdir()
        self.start("iron-fillet", directory)
        record = self.record_for("iron-fillet")
        self.assertEqual(record["cwd"], str(directory))
        # --remote-control is a boolean flag in agy (must NOT receive session name).
        self.assertEqual(self.launch_args(record), ["--dangerously-skip-permissions", "--remote-control"])
        self.assertTrue(record["tty"])
        self.assertFalse((ROOT / "INJECTED").exists())
        self.assertEqual(self.run_helper("list").stdout.strip(), "iron-fillet")

    def test_hook_registration_preserves_existing_hooks_and_ignores_subagents(self):
        self.hooks_file.parent.mkdir(parents=True)
        existing_fleet = {"SessionStart": [{"type": "command", "command": "fleet-hook"}]}
        self.hooks_file.write_text(json.dumps({"fleet": existing_fleet}))

        self.start()
        hooks = json.loads(self.hooks_file.read_text())
        self.assertEqual(hooks["fleet"], existing_fleet)
        self.assertIn("agy-session", hooks)
        self.assertTrue(hooks["agy-session"]["enabled"])
        self.assertEqual([e for e in ("SessionStart", "PreInvocation") if e in hooks["agy-session"]],
                         ["SessionStart", "PreInvocation"])
        before_text = self.hooks_file.read_text()

        # Starting a second session does not rewrite hooks.json when unchanged.
        self.start("second")
        self.assertEqual(self.hooks_file.read_text(), before_text)

        # Direct __hook invocation always returns {} on stdout, even without target or for subagents.
        res_unmanaged = self.run_helper("__hook", stdin_text=json.dumps({
            "conversationId": str(uuid.uuid4()), "cwd": str(self.base), "transcriptPath": ""
        }))
        self.assertEqual(json.loads(res_unmanaged.stdout), {})

        pane = self.pane_for("example")
        original = self.record_for("example")
        tmux_env = dict(self.env, AGY_SESSION_TARGET="tmux", AGY_SESSION_NAME="example", TMUX_PANE=pane)
        for extra in ({"agentId": "sub-1"}, {"parentConversationId": original["id"]}, {"isSubagent": True}):
            payload = {"conversationId": str(uuid.uuid4()), "cwd": str(self.base), "transcriptPath": ""}
            payload.update(extra)
            res = self.run_helper("__hook", env=tmux_env, stdin_text=json.dumps(payload))
            self.assertEqual(json.loads(res.stdout), {})

        # Main session tracking was NOT overwritten by subagent payloads.
        tracked = json.loads(self.tmux_run("show-options", "-pv", "-t", pane, "@agy_session"))
        self.assertEqual(tracked["id"], original["id"])

    def test_duplicate_does_not_replace_session(self):
        self.start()
        result = self.run_helper("start", "example", str(self.base), success=False)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.run_helper("list").stdout.strip(), "example")

    def test_noninteractive_ssh_path(self):
        local_bin = self.base / ".local/bin"
        local_bin.mkdir(parents=True)
        (self.bin / "agy").rename(local_bin / "agy")
        self.env.update(HOME=str(self.base), PATH=f"{self.bin}:/usr/bin:/bin")
        self.start()
        self.assertEqual(self.launch_args(self.record_for()), ["--dangerously-skip-permissions", "--remote-control"])

    def test_upgrade_brew_stops_all_then_resumes_exact_conversations_in_same_panes(self):
        directory = self.base / "space ' quote; $(touch INJECTED)"
        directory.mkdir()
        self.start("first", directory)
        self.start("second", directory)
        before = {name: self.record_for(name) for name in ("first", "second")}
        panes = {name: self.pane_for(name) for name in before}
        # Extra shell pane, unrelated session, and claude-* session stay untouched.
        extra = self.tmux_run("split-window", "-d", "-P", "-F", "#{pane_id}",
                              "-t", "=agy-first:", "tmux", "wait-for", "release")
        self.tmux_run("new-session", "-d", "-s", "unrelated", "tmux", "wait-for", "release")
        self.tmux_run("new-session", "-d", "-s", "claude-other", "tmux", "wait-for", "release")
        self.tmux_run("set-option", "-p", "-t", panes["second"], "remain-on-exit", "failed")
        log = (self.base / "client.log").open("w")
        self.addCleanup(log.close)
        client = subprocess.Popen(
            [self.tmux, "-L", self.socket, "-C", "attach-session", "-t", "=agy-first"],
            env=self.env,
            text=True,
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=log,
        )
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
                self.assertEqual(
                    self.launch_args(after),
                    ["--dangerously-skip-permissions", "--remote-control", "--conversation", original["id"]],
                )
            self.assertIsNone(client.poll(), "Attached tmux client disconnected during upgrade")
            brew = json.loads((self.base / "brew.json").read_text())
            self.assertEqual(brew["args"], ["upgrade", "--cask", "antigravity-cli"])
            for row in brew["panes"]:
                session, pane, dead = row.split()
                self.assertEqual(dead, "1" if pane in panes.values() else "0", session)
            self.assertEqual(self.tmux_run("display-message", "-p", "-t", panes["first"], "#{remain-on-exit}"), "off")
            self.assertEqual(self.tmux_run("display-message", "-p", "-t", panes["second"], "#{remain-on-exit}"), "failed")
        self.assertFalse((ROOT / "INJECTED").exists())

    def test_upgrade_self_update_stops_all_then_resumes_exact_conversations(self):
        # Standalone install (~/.local/bin/agy, not managed by brew cask).
        local_bin = self.base / ".local/bin"
        local_bin.mkdir(parents=True)
        (self.bin / "agy").rename(local_bin / "agy")
        self.install_fake_brew(cask_installed=False)
        env = dict(self.env, PATH=f"{local_bin}:{self.bin}:/usr/bin:/bin")

        self.run_helper("start", "example", str(self.base), env=env)
        self.wait_ready("example")
        original = self.record_for("example")

        result = self.run_helper("upgrade", env=env)
        self.assertIn("Resumed example", result.stdout)
        self.wait_ready("example")
        after = self.record_for("example")
        self.assertEqual(after["id"], original["id"])
        self.assertNotEqual(after["pid"], original["pid"])
        self.assertFalse((self.base / "brew.json").exists())
        self.assertEqual(json.loads((self.base / "update.json").read_text())["args"], ["update"])

        # Failure and interruption during `agy update` still restore sessions and clear lock.
        for failure in ({"FAKE_UPDATE_STATUS": "19"}, {"FAKE_UPDATE_INTERRUPT": "1"}):
            with self.subTest(failure=failure):
                before_fail = self.record_for("example")
                res = self.run_helper("upgrade", env=dict(env, **failure), success=False)
                self.assertEqual(res.returncode, 19 if "FAKE_UPDATE_STATUS" in failure else 143)
                self.wait_ready("example")
                self.assertEqual(self.record_for("example")["id"], before_fail["id"])
                self.assertNotEqual(self.record_for("example")["pid"], before_fail["pid"])
                self.assertFalse((self.base / "state/agy-session/upgrade.lock").exists())

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
                self.assertFalse((self.base / "state/agy-session/upgrade.lock").exists())

    def test_upgrade_preflights_all_sessions_before_stopping_any(self):
        self.start("first")
        original = self.record_for("first")
        self.tmux_run("new-session", "-d", "-s", "agy-old", "agy")
        self.wait_rex_ready("unnamed")
        result = self.run_helper("upgrade", success=False)
        self.assertIn("restart it with the updated", result.stderr)
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", "=agy-first:", "#{pane_pid}"), str(original["pid"]))
        self.assertFalse((self.base / "brew.json").exists())

    def test_upgrade_requires_saved_conversation(self):
        self.start()
        original = self.record_for()
        (self.base / (original["id"] + ".jsonl")).unlink()
        result = self.run_helper("upgrade", success=False)
        self.assertIn("Send a message", result.stderr)
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", self.pane_for(), "#{pane_pid}"), str(original["pid"]))
        self.assertFalse((self.base / "brew.json").exists())

        # A freshly started managed session that hasn't fired SessionStart yet also fails preflight.
        self.run_helper("start", "idle-new", str(self.base), env=dict(self.env, FAKE_SKIP_SESSION_START="1"))
        self.wait_ready("idle-new")
        res_idle = self.run_helper("upgrade", success=False)
        self.assertIn("Send a message", res_idle.stderr)
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
        self.assertEqual(json.loads(self.tmux_run("show-options", "-pv", "-t", pane, "@agy_session"))["id"], original["id"])
        self.tmux_run("set-environment", "-gu", "FAKE_RESUME_FAIL")
        self.run_helper("upgrade")
        self.wait_ready()
        self.assertEqual(self.record_for()["id"], original["id"])
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", pane, "#{remain-on-exit}"), "off")

    def test_interruption_during_shutdown_still_restores_session(self):
        self.start()
        original = self.record_for()
        (self.base / "hold-stop").touch()
        process = subprocess.Popen(
            ["bash", str(HELPER), "upgrade"],
            cwd=ROOT,
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
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
        (self.base / "state/agy-session/upgrade.lock").mkdir(parents=True)
        self.assertIn("Another upgrade", self.run_helper("upgrade", success=False).stderr)
        self.assertIn("upgrade is running", self.run_helper("start", "second", str(self.base), success=False).stderr)
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", self.pane_for(), "#{pane_pid}"), str(original["pid"]))
        self.assertFalse((self.base / "brew.json").exists())

    def test_stale_tracking_does_not_stop_a_replacement_process(self):
        self.start()
        pane = self.pane_for()
        state = json.loads(self.tmux_run("show-options", "-pv", "-t", pane, "@agy_session"))
        state["pid"] = "0"
        self.tmux_run("set-option", "-p", "-t", pane, "@agy_session", json.dumps(state))
        self.assertIn("tracking is not ready", self.run_helper("upgrade", success=False).stderr)
        self.assertFalse((self.base / "brew.json").exists())

    def test_upgrade_without_sessions(self):
        self.run_helper("upgrade")
        self.assertEqual(json.loads((self.base / "brew.json").read_text())["args"],
                         ["upgrade", "--cask", "antigravity-cli"])

        # Self-update without sessions also succeeds without requiring brew.
        local_bin = self.base / ".local/bin"
        local_bin.mkdir(parents=True)
        (self.bin / "agy").rename(local_bin / "agy")
        (self.bin / "brew").unlink()
        env = dict(self.env, PATH=f"{local_bin}:{self.bin}:/usr/bin:/bin")
        self.run_helper("upgrade", env=env)
        self.assertEqual(json.loads((self.base / "update.json").read_text())["args"], ["update"])

    def test_upgrade_resolves_replacement_executable_and_antigravity_binary_name(self):
        self.start()
        original = self.record_for()
        # Replace agy with a wrapper that execs a binary named `antigravity`,
        # matching Homebrew cask's command_wrapper behavior.
        self.install_fake_agy("antigravity")
        self.write_executable("agy-new", f'#!/bin/sh\nexec {shlex.quote(str(self.bin / "antigravity"))} "$@"\n')
        self.write_executable("agy", "#!/bin/sh\nexit 99\n")
        self.run_helper("upgrade")
        self.wait_ready()
        after = self.record_for()
        self.assertEqual(after["id"], original["id"])
        self.assertEqual(after["exe"], "antigravity")
        self.assertEqual(self.run_helper("list").stdout.strip(), "example")

    def test_tracking_follows_resume_or_new_via_pre_invocation(self):
        self.start()
        hooks = json.loads(self.hooks_file.read_text())
        hook_cmd = hooks["agy-session"]["PreInvocation"][0]["command"]
        new_id = str(uuid.uuid4())
        transcript = self.base / (new_id + ".jsonl")
        transcript.touch()
        res = subprocess.run(
            hook_cmd,
            shell=True,
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
            env=dict(self.env, AGY_SESSION_TARGET="tmux", AGY_SESSION_NAME="example", TMUX_PANE=self.pane_for()),
            input=json.dumps({
                "conversationId": new_id,
                "cwd": str(self.base),
                "transcriptPath": str(transcript),
                "hookEventName": "PreInvocation",
            }),
        )
        self.assertEqual(json.loads(res.stdout), {})
        self.run_helper("upgrade")
        self.wait_ready()
        self.assertEqual(self.record_for()["id"], new_id)

    def test_attach_requires_exact_name(self):
        self.start("example-long")
        self.run_helper("attach", "example", success=False)
        self.run_helper("attach", "example-long")
        self.assertEqual((self.base / "attach").read_text(), "attach-session\n-t\n=agy-example-long\n")

    def test_attach_inside_tmux_switches_client(self):
        self.start()
        env = dict(self.env, TMUX="existing-client")
        self.run_helper("attach", "example", env=env)
        self.assertEqual((self.base / "attach").read_text(), "switch-client\n-t\n=agy-example\n")

    def test_start_attach_creates_session_then_attaches_or_switches_client(self):
        for name, env, command in (
            ("terminal", self.env, "attach-session"),
            ("nested", dict(self.env, TMUX="existing-client"), "switch-client"),
        ):
            with self.subTest(name=name):
                self.run_helper("start-attach", name, str(self.base), env=env)
                self.wait_ready(name)
                self.assertEqual(self.record_for(name)["cwd"], str(self.base))
                self.assertEqual((self.base / "attach").read_text(), f"{command}\n-t\n=agy-{name}\n")

    def test_start_attach_rejects_duplicate_without_attaching(self):
        self.start()
        original = self.record_for()
        result = self.run_helper("start-attach", "example", str(self.base), success=False)
        self.assertIn("already exists", result.stderr)
        self.assertFalse((self.base / "attach").exists())
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", self.pane_for(), "#{pane_pid}"), str(original["pid"]))

    def test_attach_sends_session_name_to_outer_terminal(self):
        self.start()
        self.tmux_run("new-session", "-d", "-s", "unrelated", "tmux", "wait-for", "release")
        before = self.tmux_run("display-message", "-p", "-t", "=unrelated:", "#{set-titles}|#{set-titles-string}")
        self.write_executable("tmux", f'#!/bin/sh\nexec {shlex.quote(self.tmux)} -L {self.socket} -f /dev/null "$@"\n')
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        client = subprocess.Popen(
            ["bash", str(HELPER), "attach", "example"],
            env=dict(self.env, TERM="xterm-256color"),
            stdin=slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
        )
        os.close(slave)

        def stop_client():
            os.close(master)
            client.kill()
            client.wait(timeout=10)

        self.addCleanup(stop_client)
        output = b""
        title = b"\x1b]0;example\x07"
        deadline = time.monotonic() + 10
        while title not in output:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([master], [], [], remaining)[0]:
                break
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
        self.assertIn(title, output)
        self.assertEqual(self.tmux_run("display-message", "-p", "-t", "=unrelated:", "#{set-titles}|#{set-titles-string}"), before)

    def test_kill_uses_exact_name_and_keeps_saved_conversation(self):
        self.start("example-long")
        self.run_helper("kill", "example", success=False)
        self.start()
        session_id = self.record_for()["id"]
        self.assertIn("Killed example", self.run_helper("kill", "example").stdout)
        self.assertEqual(self.run_helper("list").stdout.strip(), "example-long")
        self.assertTrue((self.base / (session_id + ".jsonl")).exists())
        self.run_helper("kill", "missing", success=False)

    def test_kill_all_only_ends_agy_sessions_and_handles_empty_server(self):
        self.assertIn("No agy sessions", self.run_helper("kill-all").stdout)
        self.start("first")
        self.start("second")
        self.tmux_run("new-session", "-d", "-s", "unrelated", "tmux", "wait-for", "release")
        self.tmux_run("new-session", "-d", "-s", "claude-other", "tmux", "wait-for", "release")
        result = self.run_helper("kill-all")
        self.assertIn("Killed first", result.stdout)
        self.assertIn("Killed second", result.stdout)
        self.assertIn("No agy sessions", self.run_helper("list").stdout)
        self.tmux_run("has-session", "-t", "=unrelated")
        self.tmux_run("has-session", "-t", "=claude-other")
        self.assertIn("No agy sessions", self.run_helper("kill-all").stdout)

    def test_kill_all_from_agy_pane_ends_its_own_session_last(self):
        self.start("first")
        self.start("second")
        self.tmux_run("new-session", "-d", "-s", "unrelated", "tmux", "wait-for", "release")
        self.tmux_run("new-window", "-d", "-t", "=agy-first:", "bash", str(HELPER), "kill-all")
        for _ in range(100):
            if "No agy sessions" in self.run_helper("list").stdout:
                break
            time.sleep(0.05)
        self.assertIn("No agy sessions", self.run_helper("list").stdout)
        self.tmux_run("has-session", "-t", "=unrelated")

    def test_empty_list_and_unrelated_sessions(self):
        self.assertIn("No agy sessions", self.run_helper().stdout)
        self.tmux_run("new-session", "-d", "-s", "unrelated", "tmux", "wait-for", "release")
        self.tmux_run("new-session", "-d", "-s", "claude-other", "tmux", "wait-for", "release")
        self.assertIn("No agy sessions", self.run_helper("list").stdout)

    def test_rex_mode_lifecycle_upgrade_and_tmux_override(self):
        rex_dir = self.install_fake_rex()
        self.write_executable("lazygit", "#!/bin/sh\nexit 0\n")
        repo = self.base / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

        # Start defaults to Rex and opens a lazygit split inside a git repo.
        self.run_helper("start", "alpha", str(repo))
        first_pid = self.wait_rex_ready("alpha")
        self.assertEqual(self.run_helper("list").stdout.strip(), "alpha (rex)")
        actions = json.loads((rex_dir / "actions.json").read_text())
        split_calls = [a["split"] for a in actions if "split" in a]
        self.assertEqual(len(split_calls), 1)
        self.assertIn("--split=right", split_calls[0])
        self.assertIn("lazygit", split_calls[0])

        # Duplicate rejected across Rex.
        dup = self.run_helper("start", "alpha", str(repo), success=False)
        self.assertIn("already exists", dup.stderr)

        # Attach selects the session in Rex app.
        self.run_helper("attach", "alpha")
        actions = json.loads((rex_dir / "actions.json").read_text())
        selects = [a for a in actions if a.get("args", [])[:2] == ["do", "session.select"]]
        self.assertEqual(len(selects), 1)

        # --tmux forces tmux even when rex is installed.
        self.run_helper("start", "--tmux", "beta", str(repo))
        self.wait_ready("beta")
        listed = self.run_helper("list").stdout.splitlines()
        self.assertEqual(sorted(listed), ["alpha (rex)", "beta"])

        # Upgrade restarts both the Rex wrapper session and the --tmux session.
        alpha_before = self.record_for("alpha")
        beta_before = self.record_for("beta")
        res = self.run_helper("upgrade")
        self.assertIn("Resumed alpha (rex)", res.stdout)
        self.assertIn("Resumed beta", res.stdout)
        second_pid = self.wait_rex_ready("alpha", prev_pid=first_pid)
        self.wait_ready("beta")
        alpha_after = self.record_for("alpha")
        beta_after = self.record_for("beta")
        self.assertEqual(alpha_after["id"], alpha_before["id"])
        self.assertNotEqual(second_pid, first_pid)
        self.assertEqual(beta_after["id"], beta_before["id"])
        self.assertNotEqual(beta_after["pid"], beta_before["pid"])

        # start-attach shows in Rex when rex_show succeeds.
        self.run_helper("start-attach", "gamma", str(repo))
        self.wait_rex_ready("gamma")

        # kill and kill-all clean up Rex sessions.
        self.assertIn("Killed alpha", self.run_helper("kill", "alpha").stdout)
        self.assertIn("gamma (rex)", self.run_helper("list").stdout)
        kill_all_res = self.run_helper("kill-all")
        self.assertIn("Killed beta", kill_all_res.stdout)
        self.assertIn("Killed gamma (rex)", kill_all_res.stdout)
        self.assertIn("No agy sessions", self.run_helper("list").stdout)

    def test_invalid_inputs(self):
        for name in ("", "-option", "bad.name", "bad:name", "a b", "$(touch INJECTED)"):
            with self.subTest(name=name):
                self.run_helper("start", name, str(self.base), success=False)
                self.run_helper("kill", name, success=False)
        self.run_helper("start", "valid", str(self.base / "missing"), success=False)
        self.run_helper("resume", "valid", str(self.base), "not-a-uuid", success=False)
        self.run_helper("attach", "missing", success=False)
        for args in (
            ("start",),
            ("start-attach",),
            ("resume",),
            ("attach",),
            ("list", "extra"),
            ("list", "--tmux"),
            ("attach", "example", "--tmux"),
            ("kill", "example", "--tmux"),
            ("kill-all", "--tmux"),
            ("upgrade", "--tmux"),
            ("kill",),
            ("kill-all", "extra"),
            ("upgrade", "extra"),
            ("unknown",),
        ):
            self.run_helper(*args, success=False)
        self.assertIn("Usage:", self.run_helper("--help").stdout)


if __name__ == "__main__":
    unittest.main()
