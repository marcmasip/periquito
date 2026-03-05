import os
import pathspec
import re

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

def read_protocol() -> str:
    """
    Reads the README.md file and extracts the content under the
    '### Project Structure' heading. If not found or empty, generates
    a root-level file listing of the project as a fallback.
    """
    readme_content = read_readme()
    protocol_content = ""

    if "No README file found." not in readme_content:
        # Use regex to find content between '### Project Structure' or '### Source' and the next heading or end of file.
        match = re.search(r'### (?:Project Structure|Source)\s*\n(.*?)(?=\n#{1,3} |\Z)', readme_content, re.DOTALL | re.IGNORECASE)
        if match and match.group(1).strip():
            protocol_content = match.group(1).strip()

    if protocol_content:
        return f"{protocol_content}"
    
    # Fallback to root directory listing
    spec = get_gitignore_spec()
    lines = []
    for item in sorted(os.listdir('.')):
        if spec.match_file(item):
            continue
        if os.path.isdir(item):
            lines.append(f"{item}/")
        else:
            lines.append(item)
    
    summary = "\n".join(lines)
    return f"No 'Project Structure' section found in README. Using a file listing summary to guide folder exploration:\n\n---\n{summary}\n---"

def parse_folders_from_protocol(protocol_content: str) -> list[str]:
    """
    Extracts folder and file paths from a markdown list in the protocol text.
    It looks for lines starting with '-' and expects a format like:
    - <path> : <optional notes>
    It accepts both files and folders that exist on the filesystem.
    """
    # Regex to find lines starting with a markdown list item ('-')
    # and capture the path that comes before an optional ':'
    paths = re.findall(r'^\s*-\s*([^:\n]+)', protocol_content, re.MULTILINE)

    # Clean up, check for existence, and remove duplicates
    unique_paths = sorted(list(set(
        p.strip() for p in paths if os.path.exists(p.strip())
    )))
    return unique_paths

def get_gitignore_spec() -> pathspec.PathSpec:
    patterns = []
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            patterns = f.read().splitlines()
    patterns.extend(['.git', '__pycache__', '.agent'])
    return pathspec.PathSpec.from_lines('gitwildmatch', patterns)

def build_tree(folders: list[str]) -> str:
    if not folders:
        return "" # Return empty string if no folders are specified

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
            context.append(f"--- FILE: {filename} ({line_count} lines)---\n{content}")
    return "\n\n".join(context)
