Forked from https://github.com/driesvints/dotfiles

---

1. Setup SSH
```
curl https://raw.githubusercontent.com/driesvints/dotfiles/HEAD/ssh.sh | sh -s "<email-address>"
```

2. Setup GitHub SSH Key https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent

3. Run init script via chezmoi toolset

```
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply git@github.com:bdatdo0601/dotfiles.git
```

4. Restart your computer to finalize the process
