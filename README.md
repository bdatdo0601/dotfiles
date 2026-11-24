# Dat DotFiles

## New machine setup

1. Setup SSH `curl https://raw.githubusercontent.com/driesvints/dotfiles/HEAD/ssh.sh | sh -s "<email-address>"`
2. Setup GitHub SSH Key [Ref](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)
3. Run init script via chezmoi toolset `sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply git@github.com:bdatdo0601/dotfiles.git` (decrypt pw keep in note)
4. install this [workflow](https://alfred.app/workflows/alfredapp/backup-preferences/) set sync folder to `$HOME/.local/share/chezmoi/alfred_pref` --> choose restore backup to the latest
5. Restart your computer to finalize the process

### What `chezmoi apply` runs

Before every chezmoi command, `.pre_setup.sh` makes sure Homebrew, the 1Password app/CLI and the
`my.1password.com` account are present (silent once they are). Secrets in `envvars.zsh` are read from
the 1Password `local` vault — enable *1Password → Settings → Developer → Integrate with 1Password CLI*
for Touch ID unlock.

After dotfiles are written, these run once each (in order). Every step is idempotent and prints
`[n/N]` progress, timings and a summary; full logs go to `~/.local/state/dotfiles/logs/`.

| Script | Does |
| --- | --- |
| `10-bootstrap` | network + sudo check, `brew update`, FileVault, Brewfile packages, rustup, uv, `~/workspace`, tmux TPM |
| `20-node` | nvm, Node LTS (only if no `node` exists yet), global pnpm CLIs |
| `30-projects` | checks GitHub SSH, clones repos for the configured email into `~/workspace` |
| `90-macos-defaults` | asks, then applies `~/.macos` (restarts Finder/Dock/Terminal…; re-runs when `.macos` changes) |

If a step fails, the script exits non-zero and chezmoi retries it on the next `chezmoi apply`;
finished steps are skipped.

| Flag | Effect |
| --- | --- |
| `INSTALL_MAS=1` | include Mac App Store apps (sign in to the App Store first, or `mas` hangs) |
| `BREW_UPGRADE=1` | upgrade already-installed Brewfile packages |
| `MACOS_DEFAULTS=yes\|no` | answer the macOS defaults prompt non-interactively |

e.g. `INSTALL_MAS=1 chezmoi apply`. To force a script to run again: `chezmoi state delete-bucket --bucket=scriptState`.

## Sync VS-Code

Login to github via vs-code to sync setting and others

Turn Sync on

## Hot Keys mapping

```markdown
Alfred --> Cmd + Ctrl + Space

Alfred File Search --> Option + Cmd + /

Alfred Universal Action --> Cmd + Ctrl + \

Alfred Clipboard --> Option + Cmd + C

Alfred Snippet --> Ctrl + Cmd + Shift + S

Homerow Click --> Cmd + Shift + Option + F

Homerow Scrolling --> Cmd + Shift + Option + J

Homerow Search --> Cmd + Shift + Option + Space
```

## Aerospace command

```markdown

<leader> is alt keys

can also be controlled by Tilling Layer via Dygma Config

configurable via dot_aerospace.toml

<leader> 0 --> 9 generic workspace

<leader> T terminal workspace

<leader> B browser workspace

<leader> N notes workspace

<leader> M meetings workspace

<leader> P players (music) workspace

<leader> C code workspace

<leader> tab switch monitor focus

<leader> shift tab --> move current workspace to next monitor

<leader> comma --> accordion view

<leader> slash --> tiles view

<leader> enter --> fullscreen current window

<leader> hjkl --> move focus between window in workspace

<leader> shift hjkl --> move window 

<leader> shift minus --> decrease window size

<leader> shift plus --> increase window size

<leader> semi-colon --> enter service mode
----
[Service Mode]

<leader> esc --> reload config (post config modification)

<leader> r --> reset window in workspace

<leader> f --> toggle workspace setup between floating and Tilling

<leader> backspace --> close non-focus window

<leader> shift hjkl --> join current window with direction
```

## NVIM Useful command

```markdown
<leader> by default is space

Ctrl + n --> File Tree

<leader> + f f --> File Search

<leader> + <leader> --> Shortcut
```

## TMUX Useful command

```markdown
<leader> by default is ctrl+b

<leader> + x --> terminate

<leader> + % --> open a new pane horizontally

<leader> + " --> open a new pane vertically

<leader> + c --> new window

<leader> + d --> detach session

<leader> + s --> switch session

<leader> + hjkl --> move focus
```

## Claude sessions over SSH and in Zed

`claude-session` is installed in `~/.customscripts` (already on PATH). It needs
tmux, jq and Claude Code, all included in the Brewfile. Sign in to Claude Code with
a Remote Control eligible Claude subscription on the host machine.

```sh
claude-session start iron ~/workspace/iron-fillet
claude-session list
claude-session attach iron
```

Start creates a detached tmux session in the given directory, running
`claude --dangerously-skip-permissions --remote-control NAME`. Names contain
letters, digits, underscores and hyphens and start with a letter or digit.
Duplicate names are rejected; attach to the existing session or choose another
name. This command grants Claude permission to run tools without approval.

To start a session and attach immediately in one command:

```sh
claude-session start-attach iron ~/workspace/iron-fillet
```

Inside tmux, this switches the current client to the new session. Duplicate names
are rejected; use `claude-session attach NAME` to enter an existing session.

In Zed, open the Agent Panel's new-thread menu, choose **Terminal**, and run
`claude-session attach iron`. The helper sets tmux's outer terminal title to
`iron`, so Zed automatically uses the session name for the Terminal Thread.
Without a terminal title, Zed falls back to the directory and process command.
The title stays fixed as Claude works and across upgrades. For an existing
session, detach and attach again to enable this; Claude does not need restarting.
If you previously set a custom Zed title, clear it using **Rename Title** to
return to the automatic title. See [Zed's Terminal Thread titles](https://zed.dev/docs/ai/terminal-threads#terminal-thread-titles).

The terminal and the Claude phone app control the same running Claude session. Attach once
after starting to complete any first-run prompts and obtain the phone link.
Use the same OS user over SSH and locally. From another machine:

```sh
ssh my-mac '~/.customscripts/claude-session start iron /absolute/project/path'
ssh -t my-mac '~/.customscripts/claude-session attach iron'
```

Detach with **Ctrl-b, then d**; `/exit` inside Claude ends the session. Keep the
host awake. SSH disconnects are safe, but rebooting ends the running sessions.
The helper creates `claude-NAME` sessions on your normal tmux server and uses
your existing tmux configuration. Calling attach from within tmux switches the
current client instead of nesting another tmux.

To end one Claude tmux session or all of them:

```sh
claude-session kill iron
claude-session kill-all
```

These commands terminate the selected sessions and all panes inside them,
including any running work, and disconnect their attached terminals. `kill-all`
selects only `claude-*` tmux sessions. Saved Claude conversation history remains
available through `claude-session resume`. Killing all sessions when none are
running succeeds without doing anything.

To upgrade Claude Code and resume all managed conversations, run this from a
separate terminal after Claude finishes its current work:

```sh
claude-session upgrade
```

The helper checks that every conversation has a saved transcript, stops Claude
with SIGTERM, runs `brew upgrade claude-code@latest`, then restarts each conversation
in its original tmux pane and directory using its exact
[`--resume` ID](https://code.claude.com/docs/en/cli-reference). Attached terminals
stay connected. Conversation history is restored and Claude waits for your next
prompt. Other tmux sessions and extra shell panes are left running.
The helper tracks the current conversation through `/clear` and `/resume` using a
[`SessionStart` hook](https://code.claude.com/docs/en/hooks#sessionstart).

If Homebrew fails or the upgrade is interrupted, the helper still attempts to
resume every stopped conversation and returns an error. Failed restarts retain
their tmux panes and conversation IDs: attach to inspect the error, fix the
installation or finish startup prompts, then rerun `claude-session upgrade`.

Sessions started before this tracking was added need a one-time restart. Inside
each existing Claude session, copy its session ID from `/status`, then `/exit`.
Reopen that conversation under the updated helper:

```sh
claude-session resume iron ~/workspace/iron-fillet SESSION_ID
```

Upgrade refuses to stop an untracked session; it never guesses which conversation
to resume when several sessions share a directory. Newly opened conversations
need at least one saved message before upgrading.

Shift-Enter inserts a newline inside tmux because `~/.config/tmux/tmux.conf`
enables tmux extended keys and Zed's terminal keymap sends Shift-Enter as
`ESC [13;2u`. After applying a tmux.conf change, restart the server with
`tmux kill-server` (this ends running sessions). Ctrl-J also inserts a newline
in any terminal.

Apply just the helper, without running chezmoi bootstrap scripts:

```sh
chezmoi apply --exclude scripts ~/.customscripts/claude-session
```

Validate from the chezmoi source root (tests use an isolated tmux server and
a fake Claude executable, with no model calls):

```sh
shellcheck dot_customscripts/executable_claude-session
python3 helpers/test_claude_session.py   # also checks tmux.conf key handling
```

## Antigravity (agy) sessions

`agy-session` in `~/.customscripts` provides the same workflow for the Antigravity
CLI (`agy`, installed via `cask 'antigravity-cli'` in `Brewfile`):

```sh
agy-session start iron ~/workspace/iron-fillet
agy-session start-attach iron ~/workspace/iron-fillet
agy-session list
agy-session attach iron
agy-session resume iron ~/workspace/iron-fillet SESSION_ID
agy-session kill iron
agy-session kill-all
agy-session upgrade
```

Sessions launch with `--dangerously-skip-permissions --remote-control`, defaulting
to Rex (with a `lazygit` pane in git repositories) or tmux when `--tmux` is passed
or `rex` is not installed. `agy-session` registers an `"agy-session"` entry for
`SessionStart` and `PreInvocation` in `~/.gemini/config/hooks.json` (preserving
existing entries like `fleet`) so `agy-session upgrade` can stop active sessions,
run `brew upgrade --cask antigravity-cli` (or `agy update` for standalone installs),
and resume each conversation with `--conversation ID` in the same pane.

Apply just the helper, without running chezmoi bootstrap scripts:

```sh
chezmoi apply --exclude scripts ~/.customscripts/agy-session
```

Validate from the chezmoi source root (tests use an isolated tmux server and
fake `agy`/`rex` executables, with no model calls):

```sh
shellcheck dot_customscripts/executable_agy-session
python3 helpers/test_agy_session.py
```

## Backups Encrypted Files

run `cmencryptbackup.sh` (located in helpers)
