#!/bin/zsh --no-rcs

# Ayai GPT Nexus alpha - launch the bundled executable
xattr -d com.apple.quarantine ./src/GPTNexus >/dev/null 2>&1
./src/GPTNexus "$1" "$2"

#$HOME${x_debug_DEV} "$1" "$2"
