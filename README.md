# Dat DotFiles

1. Setup SSH `curl https://raw.githubusercontent.com/driesvints/dotfiles/HEAD/ssh.sh | sh -s "<email-address>"`
2. Setup GitHub SSH Key [Ref](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)
3. Run init script via chezmoi toolset `sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply git@github.com:bdatdo0601/dotfiles.git` (decrypt pw keep in note)
4. install this [workflow](https://alfred.app/workflows/alfredapp/backup-preferences/) set sync folder to `$HOME/.local/share/chezmoi/alfred_pref` --> choose restore backup to the latest
5. Restart your computer to finalize the process

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

## Backups Encrypted Files

run `cmencryptbackup.sh` (located in helpers)
