import json
import subprocess
import os
import difflib # Added for detailed diff view
from . import print as printer

def _run_command(command):
    """Executes a command and returns its output."""
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        printer.error(f"Error executing command: {' '.join(command)}")
        printer.error(f"Stderr: {e.stderr}")
        return None

def preview(patch_path: str) -> str:
    """
    Presents a summary of changes, allows viewing detailed diffs,
    and returns 'apply', 'skip', or 'retry' based on user input.
    """
    printer.header(f"Previewing changes from {patch_path}")
    try:
        with open(patch_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        printer.error(f"Error reading patch file: {e}")
        return False # Cannot preview, so cannot apply

    explanation = data.get('explanation', 'No explanation provided.')
    printer.panel(explanation, title="Explanation")

    changes = data.get('changes', [])
    if not changes:
        printer.info("No changes proposed.")
        return 'skip' # No changes, so nothing to apply

    printer.header("Summary of Proposed Changes")
    
    # Stores (display_index, original_change_index) for interactive selection
    selectable_changes_map = {} 
    current_display_idx = 1
    
    # Group changes by file for better presentation
    grouped_file_changes = {}
    for i, change in enumerate(changes):
        file = change.get('file')
        if file not in grouped_file_changes:
            grouped_file_changes[file] = []
        grouped_file_changes[file].append((i, change)) # Store original index and change data

    for file_path, file_change_list in grouped_file_changes.items():
        printer.info(f"File: {file_path}")
        for original_idx, change in file_change_list:
            search_block = change.get('search', '')
            replace_block = change.get('replace', '')

            summary = ""
            if not search_block:
                lines_added = len(replace_block.splitlines())
                summary = f"Create new file ({lines_added} lines)"
            else:
                search_lines = len(search_block.splitlines())
                replace_lines = len(replace_block.splitlines())
                
                if search_lines == replace_lines:
                    summary = f"Modify ({search_lines} lines changed)"
                elif search_lines == 0: # Pure addition within a file
                    summary = f"Add {replace_lines} lines"
                elif replace_lines == 0: # Pure removal within a file
                    summary = f"Remove {search_lines} lines"
                else: # Mixed change
                    summary = f"Modify (removed {search_lines}, added {replace_lines} lines)"
            
            printer.sub_info(f"[{current_display_idx}] {summary}")
            selectable_changes_map[current_display_idx] = original_idx
            current_display_idx += 1
    
    print()

    # Interactive menu loop
    while True:
        printer.wisp(
            "Options:\n"
            "  <number> : View detailed diff for a specific change.\n"
            "  'a'      : Proceed to apply changes (default).\n"
            "  's'      : Skip applying changes.\n"
            "  'i'      : Report an issue and iterate/retry generation.\n"
            "  'q'      : Quit and skip applying changes."
        )

        choice = printer.ask("Enter your choice (a): ").lower()

        if choice == 'a' or choice == '':
            printer.info("Proceeding with application...")
            return 'apply'
        elif choice == 's' or choice == 'q':
            printer.info("Skipping changes as requested.")
            return 'skip'
        elif choice == 'i' or choice == 'r':
            return 'iterate'

        try:
            selected_display_idx = int(choice)
            original_idx = selectable_changes_map.get(selected_display_idx)
            
            if original_idx is not None:
                change = changes[original_idx] # Retrieve the full change data
                file = change.get('file')
                search = change.get('search', '')
                replace = change.get('replace', '')
                
                title = f"Detailed View for {file} (Change {selected_display_idx})"
                if not search:
                    content = f"Action: Create new file.\n---\n{replace}"
                    printer.panel(content, title=title)
                else:
                    diff = difflib.unified_diff(
                        search.splitlines(keepends=True),
                        replace.splitlines(keepends=True),
                        fromfile=f"a/{file}",
                        tofile=f"b/{file}",
                        lineterm=''
                    )
                    diff_content = "".join(list(diff))
                    printer.panel(diff_content, title=title)
            else:
                printer.warning("Invalid number. Please try again.")
        except ValueError:
            printer.warning("Invalid choice. Please enter a number, 'a', 's', or 'q'.")

def _preflight_check(changes) -> bool:
    """Performs checks before applying any changes."""
    printer.info("Performing pre-flight checks...")
    for i, change in enumerate(changes):
        file_path = change.get('file')
        search_block = change.get('search', '')

        if not file_path:
            printer.error(f"Pre-flight check failed: Change block {i+1} is missing 'file' key.")
            return False

        if not search_block: # Creating a new file
            # Check if target file already exists
            if os.path.exists(file_path):
                printer.error(f"Pre-flight check failed for {file_path}: File already exists, but 'search' block is empty (intended for creation).")
                return False
            # Check if parent directory exists or if we can infer it's creatable
            dir_name = os.path.dirname(file_path)
            if dir_name and not os.path.isdir(dir_name) and os.path.exists(dir_name):
                 printer.error(f"Pre-flight check failed for {file_path}: Target directory '{dir_name}' exists but is not a directory.")
                 return False
        else: # Modifying an existing file
            if not os.path.exists(file_path):
                printer.error(f"Pre-flight check failed for {file_path}: File not found for modification.")
                return False
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if search_block not in content:
                    printer.error(f"Pre-flight check failed for {file_path}: Search block not found in content.")
                    return False
            except Exception as e:
                printer.error(f"Pre-flight check failed reading {file_path}: {e}")
                return False
    printer.success("Pre-flight checks passed.")
    return True

def apply(patch_path: str) -> bool:
    """Applies the changes from the patch file."""
    printer.header(f"Applying changes from {patch_path}")
    try:
        with open(patch_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        printer.error(f"Error reading patch file: {e}")
        return False

    changes = data.get('changes', [])
    if not changes:
        printer.info("No changes to apply.")
        return True

    if not _preflight_check(changes):
        printer.error("Patch application aborted due to pre-flight check failures.")
        return False

    applied_files = set()
    for change in changes:
        file_path = change.get('file')
        search_block = change.get('search', '')
        replace_block = change.get('replace', '')

        try:
            if not search_block: # Create new file
                dir_name = os.path.dirname(file_path)
                if dir_name: # Only try to create if there's a directory component
                    os.makedirs(dir_name, exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(replace_block)
                printer.success(f"Created: {file_path}")
            else: # Search and replace
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content.replace(search_block, replace_block, 1)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                printer.success(f"Modified: {file_path}")
            
            applied_files.add(file_path) # Add to applied only on success
        except Exception as e:
            printer.error(f"An error occurred during application for {file_path}: {e}. Aborting.")
            if applied_files: # Only restore if some files were already applied
                printer.info(f"Attempting to restore {len(applied_files)} modified files...")
                _run_command(['git', 'restore'] + list(applied_files))
            return False
            
    print()
    printer.success("All changes applied successfully.")
    return True
