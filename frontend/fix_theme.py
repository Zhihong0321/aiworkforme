import os
import re

directories = [
    r"e:\AIworkforMe\frontend\src\views",
    r"e:\AIworkforMe\frontend\src\components",
    r"e:\AIworkforMe\frontend\src\App.vue"
]

replacements = [
    # Remove dark theme wrappers
    (r"\bbg-onyx\b", "bg-white"),
    (r"\bbg-mobile-aurora\b", "hidden"),
    (r"\bglass-panel-light\b", "bg-white border border-slate-200 shadow-sm"),
    (r"\bglass-panel\b", "bg-white border border-slate-200 shadow-sm"),
    
    # Backgrounds
    (r"\bbg-slate-900/\[?\d+%?\]?\b", "bg-slate-50"),
    (r"\bbg-slate-900\b", "bg-slate-50"),
    (r"\bbg-slate-800/\[?\d+%?\]?\b", "bg-white"),
    (r"\bbg-slate-800\b", "bg-slate-100"),
    (r"\bbg-slate-700/\[?\d+%?\]?\b", "bg-slate-100"),
    (r"\bbg-slate-700\b", "bg-slate-200"),
    
    # Texts
    (r"\btext-slate-200\b", "text-slate-700"),
    (r"\btext-slate-300\b", "text-slate-700"),
    (r"\btext-slate-400\b", "text-slate-500"),
    (r"\btext-slate-500\b", "text-slate-600"),
    (r"\btext-aurora\b", "text-blue-600"),
    
    # Usually text-white is used inside dark panels. 
    # But wait, if it's on a button (like bg-blue-500 text-white), changing it to text-slate-900 makes the button text dark!
    # Instead of blindly changing text-white, let's change text-white to text-slate-900 ONLY if it's in a previously dark panel. 
    # It's hard to contextualize with regex. I will change text-white to text-slate-900 and fix up explicit bg-blue buttons.
    (r"\btext-white\b", "text-slate-900"),
    
    # Borders
    (r"\bborder-slate-800/50\b", "border-slate-200"),
    (r"\bborder-slate-800\b", "border-slate-300"),
    (r"\bborder-slate-700/50\b", "border-slate-200"),
    (r"\bborder-slate-700/30\b", "border-slate-200"),
    (r"\bborder-slate-700/80\b", "border-slate-200"),
    (r"\bborder-slate-700\b", "border-slate-200"),
    (r"\bborder-slate-600\b", "border-slate-300"),
    
    # Hovers
    (r"\bhover:text-white\b", "hover:text-slate-900"),
    (r"\bhover:bg-slate-700\b", "hover:bg-slate-200"),
    (r"\bhover:bg-slate-800\b", "hover:bg-slate-100"),
    (r"\bhover:bg-slate-800/50\b", "hover:bg-slate-100"),
    
    # Special
    (r"\bbg-aurora-gradient\b", "bg-blue-600 text-white shadow-sm hover:bg-blue-700"),
    (r"opacity-40", "opacity-10"), # dampen aurora backgrounds
]

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    new_content = content
    for old, new in replacements:
        new_content = re.sub(old, new, new_content)
        
    # specific fixups to preserve white text on colored buttons
    # bg-blue-500 text-slate-900 -> bg-blue-500 text-white
    new_content = re.sub(r"\bbg-([a-z]+)-(500|600)\s+text-slate-900\b", r"bg-\1-\2 text-white", new_content)
    new_content = re.sub(r"\btext-slate-900\s+bg-([a-z]+)-(500|600)\b", r"text-white bg-\1-\2", new_content)
    new_content = re.sub(r"bg-blue-600 text-white shadow-sm hover:bg-blue-700 text-slate-900", "bg-blue-600 text-white shadow-sm hover:bg-blue-700", new_content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

files_changed = 0

for path in directories:
    if os.path.isfile(path):
        if process_file(path):
            files_changed += 1
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.vue'):
                    if process_file(os.path.join(root, file)):
                        files_changed += 1

print(f"Refactor complete. Changed {files_changed} files.")
