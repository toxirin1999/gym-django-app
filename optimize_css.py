
import os

path = r"c:\Users\kure_\Desktop\app\a\gymproject\entrenos\static\entrenos\css\entrenamiento_activo.css"

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines are 0-indexed in list.
# 1-indexed start line to remove: 4397
# 1-indexed end line to remove: 4692 (inclusive)

start_index = 4397 - 1
end_index = 4692 - 1

# We want to keep lines before start_index and lines after end_index.
# slice: lines[:start_index] + lines[end_index + 1:]

new_lines = lines[:start_index] + lines[end_index + 1:]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Removed lines {start_index+1} to {end_index+1}. Total lines removed: {end_index - start_index + 1}")
