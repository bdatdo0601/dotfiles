#!/bin/bash
# chezmoi hook (hooks.read-source-state.pre): runs before EVERY chezmoi command.
# It makes sure the tools that templates depend on exist — Homebrew and the
# 1Password CLI (envvars.zsh.tmpl reads secrets via onepasswordRead) — and must
# stay fast and silent once the machine is bootstrapped.
set -u

OP_ACCOUNT_ADDRESS="my.1password.com"
OP_ACCOUNT_EMAIL="dat.b.do@gmail.com"

say() { printf '\033[1;34m==>\033[0m \033[1m%s\033[0m\n' "$*" >&2; }

# --- Homebrew ---------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$b" ] && eval "$("$b" shellenv)" && break
  done
fi
if ! command -v brew >/dev/null 2>&1; then
  say "Installing Homebrew (asks for your password; installs Xcode Command Line Tools if needed)"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || exit 1
  eval "$(/opt/homebrew/bin/brew shellenv)"
  grep -qs 'brew shellenv' "$HOME/.zprofile" || echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
fi

# --- 1Password app + CLI ------------------------------------------------------
if [ ! -d "/Applications/1Password.app" ]; then
  say "Installing 1Password app"
  brew install --cask 1password || exit 1
fi
if ! command -v op >/dev/null 2>&1; then
  say "Installing 1Password CLI"
  brew install --cask 1password-cli || exit 1
fi

if ! op account list 2>/dev/null | grep -q "$OP_ACCOUNT_ADDRESS"; then
  say "Signing in to 1Password ($OP_ACCOUNT_ADDRESS) — secrets for envvars.zsh are read from its 'local' vault"
  echo "    Tip: in the 1Password app, enable Settings → Developer → 'Integrate with 1Password CLI'" >&2
  echo "    to unlock with Touch ID instead of typing your Secret Key and password." >&2
  op account add --address "$OP_ACCOUNT_ADDRESS" --email "$OP_ACCOUNT_EMAIL" || exit 1
fi
exit 0
