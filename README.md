Forked from https://github.com/driesvints/dotfiles

---

1. Setup SSH
```
curl https://raw.githubusercontent.com/driesvints/dotfiles/HEAD/ssh.sh | sh -s "<email-address>"
```

2. Setup GitHub SSH Key https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent

3. Clone/Pull dotfiles repo directly in home directory
```
cd ~
git init
git remote add origin git@github.com:bdatdo0601/dotfiles.git
git pull origin main
```

4. For Fresh Mac, run
```
./fresh.sh
```

5. Start `Herd.app` and run its install process
6. After mackup is synced with your cloud storage, restore preferences by running `mackup restore`
7. Restart your computer to finalize the process
