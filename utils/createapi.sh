#!/bin/bash

# Function to process a directory
process_directory() {
    local dir="$1"
    echo "----------------------------------------"
    echo "Processing directory: $dir"

    # Check if app.py exists in the directory
    if [ -f "${dir}index.py" ]; then
        echo "Running index.py in $dir"
        # Change to the directory and run app.py
        (cd "$dir" && python3 index.py > schema.json)

        # Check if the command was successful
        if [ $? -eq 0 ]; then
            echo "Successfully executed index.py in $dir"
        else
            echo "Error running index.py in $dir"
        fi
    else
        echo "Warning: index.py not found in $dir"
    fi
    echo "----------------------------------------"
}

# Find all directories named 'functions'
find src -type d -name "functions" | while read -r functions_dir; do
    echo "Found functions directory: $functions_dir"

    # Process each subdirectory within the functions directory
    for dir in "$functions_dir"/*/; do
        if [ -d "$dir" ]; then
            process_directory "$dir"
        fi
    done
done
