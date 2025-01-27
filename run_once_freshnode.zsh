#!/bin/zsh
source $HOME/.zshrc
nvm use --lts

pnpm setup
pnpm install -g @aws-amplify/cli
pnpm install -g @biomejs/biome
