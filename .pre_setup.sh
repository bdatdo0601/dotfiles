#!/bin/sh
# Check for Homebrew and install if we don't have it
# Hash to watch brewfile content {{ include "Brewfile" | sha256sum }}
if test ! $(which brew); then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> $HOME/.zprofile
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# Update Homebrew recipes
brew update

# Install all our dependencies with bundle (See Brewfile)
brew bundle --file ./Brewfile

# Setup 1Password
ONE_PASSWORD_SUBDOMAIN=my
if ! op account list | grep -q "$ONE_PASSWORD_SUBDOMAIN.1password.com"; then
  op account add --address $ONE_PASSWORD_SUBDOMAIN.1password.com --email dat.b.do@gmail.com
fi
