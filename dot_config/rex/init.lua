-- Rex config migrated from tmux (~/.config/tmux/tmux.conf) and iTerm2.

-- cmd+k clears the terminal (user's choice); the session picker moves to shift+cmd+k.
rex.bind("cmd+k", "com.superlogical.terminal.clear")
rex.bind("shift+cmd+k", "session.switch")

-- tmux: ~/.config/tmux/tmux.conf (prefix ctrl+b)
rex.bind("ctrl+b>ctrl+b", "pane.send_key", { key = "ctrl+b" })        -- :13
rex.bind("ctrl+b>h", "pane.focus", { direction = "left" })              -- :16
rex.bind("ctrl+b>j", "pane.focus", { direction = "down" })              -- :17
rex.bind("ctrl+b>k", "pane.focus", { direction = "up" })                -- :18
rex.bind("ctrl+b>l", "pane.focus", { direction = "right" })             -- :19
rex.bind("alt+left", "pane.focus", { direction = "left" })              -- :28
rex.bind("alt+right", "pane.focus", { direction = "right" })            -- :29
rex.bind("alt+up", "pane.focus", { direction = "up" })                  -- :30
rex.bind("alt+down", "pane.focus", { direction = "down" })              -- :31
rex.bind("shift+left", "client.tab.previous")                           -- :34
rex.bind("shift+right", "client.tab.next")                              -- :35
rex.bind("alt+shift+h", "client.tab.previous")                          -- :38
rex.bind("alt+shift+l", "client.tab.next")                              -- :39
rex.bind("ctrl+b>shift+'", "pane.split", { direction = "down" })        -- :58
rex.bind("ctrl+b>shift+5", "pane.split", { direction = "right" })       -- :59
