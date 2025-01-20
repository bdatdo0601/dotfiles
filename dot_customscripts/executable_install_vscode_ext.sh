#!/bin/bash

# Check if 'code' command exists
if command -v code &> /dev/null; then
    # Read code extensions from file and sort
    code_extensions=$(cat "$HOME/vscodeext.txt" | sort)

    # Get currently installed extensions and sort
    installed_extensions=$(code --list-extensions | sort)

    # Find uninstalled extensions
    uninstalled_extensions=$(comm -23 <(echo "$code_extensions") <(echo "$installed_extensions"))

    echo -n "Checking for uninstalled VSCode extensions..."

    if [ -z "$uninstalled_extensions" ]; then
        echo -e "\rall good!"
    else
        count=$(echo "$uninstalled_extensions" | wc -l)
        echo -e "\rfound $count."

        while IFS= read -r extension; do
            echo "Installing $extension..."
            code --install-extension "$extension"
        done <<< "$uninstalled_extensions"

        echo 'Done!'
    fi
fi