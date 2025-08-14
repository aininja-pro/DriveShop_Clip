#!/usr/bin/env python3
"""
Script to clean up app.py by removing old Strategic Intelligence code
"""

# Read the file
with open('src/dashboard/app.py', 'r') as f:
    lines = f.readlines()

# Find the markers
start_marker = "# Remove all old Strategic Intelligence code"
end_marker = "# ========== EXPORT TAB =========="

start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if start_marker in line:
        start_idx = i
    if end_marker in line:
        end_idx = i
        break

if start_idx is not None and end_idx is not None:
    # Keep everything up to start_idx (inclusive) and from end_idx onwards
    new_lines = lines[:start_idx+2] + ["\n"] + lines[end_idx:]
    
    # Write back
    with open('src/dashboard/app.py', 'w') as f:
        f.writelines(new_lines)
    
    print(f"Removed {end_idx - start_idx - 2} lines of old code")
else:
    print("Could not find markers")