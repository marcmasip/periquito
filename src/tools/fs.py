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
        match = re.search(r'# (?:Project Structure|Source|Agent)\s*\n(.*?)(?=\n#{1,3} |\Z)', readme_content, re.DOTALL | re.IGNORECASE)
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

def build_tree(paths: list[str]) -> str:
    if not paths:
        return "" # Devuelve string vacío si no hay rutas

    spec = get_gitignore_spec()
    
    # 1. Estructura interna para almacenar el árbol (evita duplicados)
    tree_dict = {}

    def add_to_tree(filepath: str, is_file: bool):
        # os.path.normpath limpia cosas como './carpeta' dejándolo en 'carpeta'
        clean_path = os.path.normpath(filepath)
        
        if clean_path == '.':
            return # Evitamos crear un nodo literal llamado '.'

        parts = clean_path.split(os.sep)
        current = tree_dict
        
        # Navegar y crear la estructura de carpetas necesaria
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        
        # Insertar el elemento final
        last_part = parts[-1]
        if is_file:
            current[last_part] = clean_path # La ruta indica que es un archivo
        else:
            if last_part not in current or not isinstance(current[last_part], dict):
                current[last_part] = {} # {} indica que es una carpeta

    # 2. Recorrer las rutas de entrada y poblar el diccionario
    for path in paths:
        if not os.path.exists(path) or spec.match_file(path):
            continue

        if os.path.isfile(path):
            add_to_tree(path, is_file=True)
        elif os.path.isdir(path):
            add_to_tree(path, is_file=False)

            for root, dirs, files in os.walk(path, topdown=True):
                # Filtrar carpetas ignoradas (modificando la lista in-place para os.walk)
                dirs[:] = [d for d in dirs if not spec.match_file(os.path.join(root, d))]
                
                if spec.match_file(root):
                    continue

                # Añadir las carpetas al árbol
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    add_to_tree(dir_path, is_file=False)

                # Añadir los archivos al árbol
                for f in files:
                    file_path = os.path.join(root, f)
                    if not spec.match_file(file_path):
                        add_to_tree(file_path, is_file=True)

    # 3. Generar el texto visual del árbol con caracteres especiales
    def render(node: dict, indent_level: int = 0) -> list[str]:
        lines = []
        # Ordenamos las claves alfabéticamente
        keys = sorted(node.keys())
        
        # Usamos 2 espacios por nivel de indentación
        indent = "  " * indent_level
        
        for key in keys:
            is_dir = isinstance(node[key], dict)
            
            if is_dir:
                # Las carpetas terminan en /: para indicar que contienen elementos
                lines.append(f"{indent}{key}/:")
                # Llamada recursiva aumentando el nivel de indentación
                lines.extend(render(node[key], indent_level + 1))
            else:
                file_path = node[key]
                try:
                    size_bytes = os.path.getsize(file_path)
                    size_kb = size_bytes / 1024
                    size_str = f"{size_kb:.1f}kb"
                    
                    if size_kb < 100:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if '\x00' not in content:
                                    lines_count = len(content.splitlines())
                                    size_str += f", {lines_count} lines"
                        except (UnicodeDecodeError, OSError):
                            pass
                except OSError:
                    size_str = "unknown size"
                
                # Los archivos se listan como items de una lista YAML
                lines.append(f"{indent}- {key} ({size_str})")
                
        return lines

    return "\n".join(render(tree_dict))

def read_files_as_context(filenames: list[str]) -> str:
    context = []
    for filename in filenames:
        content = read_file(filename)
        if content:
            line_count = len(content.splitlines())
            context.append(f"--- FILE: {filename} ({line_count} lines)---\n{content}")
    return "\n\n".join(context)
