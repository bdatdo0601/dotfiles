#!/bin/sh

# Install Rust
if test ! $(which rustup); then
  /bin/sh -c "$(curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs)"
fi

# Check for Homebrew and install if we don't have it
# Hash to watch brewfile content {{ include "Brewfile" | sha256sum }}
if test ! $(which brew); then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> $HOME/.zprofile
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# Setup 1Password
ONE_PASSWORD_SUBDOMAIN=my
op account add --address $ONE_PASSWORD_SUBDOMAIN.1password.com --email {{ .personal_email }}

# Install nvm (node)
if test ! $(which nvm); then
  /bin/sh -c "$(curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh)"
fi

# Update Homebrew recipes
brew update

# Install all our dependencies with bundle (See Brewfile)
brew bundle --file ./Brewfile

# Install TPM
if [ ! "$(ls -A ~/.tmux/plugins/tpm 2>/dev/null)" ]; then
  git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
fi
