import os
import pathspec

def read_file(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except (FileNotFoundError, UnicodeDecodeError):
        return ""

def read_readme() -> str:
    for name in ['readme.md', 'README.md', 'README.rst', 'README']:
        if os.path.exists(name):
            return read_file(name)
    return "No README file found."

def get_gitignore_spec() -> pathspec.PathSpec:
    patterns = []
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            patterns = f.read().splitlines()
    patterns.extend(['.git', '__pycache__', '.agent'])
    return pathspec.PathSpec.from_lines('gitwildmatch', patterns)

def build_tree(folders: list[str]) -> str:
    if not folders:
        folders = ['.'] # Default to current directory if no folders are specified

    spec = get_gitignore_spec()
    tree_lines = []

    for folder in folders:
        if not os.path.isdir(folder):
            if os.path.exists(folder) and not spec.match_file(folder):
                tree_lines.append(folder)
            continue
        
        # Add the folder name itself
        tree_lines.append(f"{folder}/")
        
        for root, dirs, files in os.walk(folder, topdown=True):
            # Filter ignored directories
            dirs[:] = [d for d in dirs if not spec.match_file(os.path.join(root, d))]
            
            if spec.match_file(root):
                continue

            # Calculate indentation level
            path_from_start = os.path.relpath(root, folder)
            if path_from_start == '.':
                level = 0
            else:
                level = len(path_from_start.split(os.sep))

            indent = '  ' * (level + 1)

            for f in files:
                file_path = os.path.join(root, f)
                if not spec.match_file(file_path):
                    tree_lines.append(f"{indent}{f}")
    
    return "\n".join(tree_lines)

def read_files_as_context(filenames: list[str]) -> str:
    context = []
    for filename in filenames:
        content = read_file(filename)
        if content:
            line_count = len(content.splitlines())
            print(f"    - Added '{filename}' ({line_count} lines)")
            context.append(f"--- FILE: {filename} ({line_count} lines)---\n{content}")
    return "\n\n".join(context)
