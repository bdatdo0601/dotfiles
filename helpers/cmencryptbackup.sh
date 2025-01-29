#!/bin/sh

echo "Encrypting"

rm -rf $HOME/.local/share/chezmoi/encrypted_alfred/
mkdir -p $HOME/.local/share/chezmoi/encrypted_alfred/

for file in $HOME/alfred_pref/*; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        echo "Encrypting $filename"
        chezmoi encrypt "$file" --output "$HOME/.local/share/chezmoi/encrypted_alfred/$filename"
    fi
done
