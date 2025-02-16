# Add directories to the PATH and prevent to add the same directory multiple times upon shell reload.
add_to_path() {
  if [[ -d "$1" ]] && [[ ":$PATH:" != *":$1:"* ]]; then
    export PATH="$1:$PATH"
  fi
}

# Load dotfiles binaries
add_to_path "$DOTFILES/bin"

# Load global Composer tools
add_to_path "$HOME/.composer/vendor/bin"

# Load global Node installed binaries
add_to_path "$HOME/.node/bin"

# Use project specific binaries before global ones
add_to_path "vendor/bin"
add_to_path "node_modules/.bin"

# Load custom scripts
add_to_path "$HOME/.customscripts"

# Load VS Code
add_to_path "/Applications/Visual Studio Code.app/Contents/Resources/app/bin"

add_to_path "$HOME/.local/share/chezmoi/helpers"

# Python
add_to_path "$HOME/.local/bin"