Forked from https://github.com/driesvints/dotfiles

---

1. Setup SSH `curl https://raw.githubusercontent.com/driesvints/dotfiles/HEAD/ssh.sh | sh -s "<email-address>"`
2. Setup GitHub SSH Key https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent
3. Run init script via chezmoi toolset `sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply git@github.com:bdatdo0601/dotfiles.git` (decrypt pw keep in note)
4. install this workflow https://alfred.app/workflows/alfredapp/backup-preferences/ set sync folder to `$HOME/.local/share/chezmoi/alfred_pref` --> choose restore backup to the latest 
5. Restart your computer to finalize the process

## Sync VS-Code

Login to github via vs-code to sync setting and others

Turn Sync on

## Hot Keys mapping

Alfred --> Cmd + Ctrl + Space

Alfred File Search --> Option + Cmd + /

Alfred Universal Action --> Cmd + Ctrl + \

Alfred Clipboard --> Option + Cmd + C

Alfred Snippet --> Ctrl + Cmd + Shift + S

Homerow Click --> Cmd + Shift + Option + F

Homerow Scrolling --> Cmd + Shift + Option + J

Homerow Search --> Cmd + Shift + Option + Space

## NVIM Useful command

```
<leader> by default is space

Ctrl + n --> File Tree

<leader> + f f --> File Search

<leader> + <leader> --> Shortcut
```

## TMUX Useful command

```
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