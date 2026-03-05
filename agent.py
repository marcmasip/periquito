#!/usr/bin/env python3
"""
agent.py  —  Dev agent with optimized context.

Usage:
    python agent.py
    python agent.py "Add dark mode support"          # non-interactive
    python -m tools.patch preview .agent/patch.json  # standalone patch preview
"""

import json, os, re, sys, io, time, subprocess
from tools import fs, phases, print as p
from tools.patch import preview, apply

AGENT_DIR = '.agent'

def _slug(text: str) -> str:
    return re.sub(r'[^a-z0-9_]', '', text.lower().replace(' ', '_'))[:50] or 'change'

def _save_patch(slug: str, solver_result) -> str:
    os.makedirs(AGENT_DIR, exist_ok=True)
    path = f"{AGENT_DIR}/{slug}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(solver_result.model_dump(), f, indent=2, ensure_ascii=False)
    return path

def _save_log(slug: str, log_content: str) -> str:
    os.makedirs(AGENT_DIR, exist_ok=True)
    path = f"{AGENT_DIR}/{slug}.txt"
    with open(path, 'w', encoding='utf-8') as f:
        f.write(log_content)
    return path

def _save_metrics(slug: str, metrics: dict) -> str:
    os.makedirs(AGENT_DIR, exist_ok=True)
    path = f"{AGENT_DIR}/{slug}_metrics.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    return path

def _run_git_command(command):
    """Executes a git command and prints its output."""
    try:
        result = subprocess.run(
            ['git'] + command,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            p.warning(result.stderr.strip())
        return True
    except subprocess.CalledProcessError as e:
        p.error(f"Error executing git command: {' '.join(['git'] + command)}")
        p.error(f"Stderr: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        p.error("Error: 'git' command not found. Is git installed and in your PATH?")
        return False

def _gather_context(request: str, history: str, metrics: dict) -> tuple[list[str] | None, str | None]:
    """Gathers context for the agent to work on by selecting folders and files."""
    protocol = fs.read_protocol()

    # Step 1: Determine folders to scan. For small projects, use all folders from protocol.
    all_protocol_folders = fs.parse_folders_from_protocol(protocol)
    folders = None
    file_tree = None

    if all_protocol_folders:
        prospective_tree = fs.build_tree(all_protocol_folders)
        if len(prospective_tree.splitlines()) < 150:
            p.header("1. 🗺️  Small project tree detected, using all protocol folders.")
            folders = all_protocol_folders
            file_tree = prospective_tree
    
    if folders is None: # Fallback for large projects or if protocol has no folders
        p.say("Exploring folders...")
        folders = phases.explore_folders(request, protocol, history, tracer=metrics)
    
    p.sub_info(f"Selected: {', '.join(folders) if folders else 'none'}")

    p.sub_info("Building file tree...")
    if file_tree is None:
        file_tree = fs.build_tree(folders)
    p.panel(file_tree)

    p.say("Picking files ...")
    files = phases.select_files(request, file_tree, history, tracer=metrics)
    p.sub_info(f"Selected: {', '.join(files) if files else 'none'}")
    
    if not files:
        p.warning("No files selected. Cannot proceed.")
        return None, None

    context = phases.build_context(files)
    lines_read = sum(int(c) for c in re.findall(r'\((\d+) lines\)', context))
    p.sub_info(f"Read {len(files)} files ({lines_read} lines) into context.")

    return files, context

def _commit_changes(request: str, solution):
    """Commits the applied changes to git."""
    p.sub_info("Committing changes via git...")
    files_to_add = list(set([change['file'] for change in solution.model_dump()['changes']]))
    _run_git_command(['add'] + files_to_add)

    commit_message = f"feat: {request}"
    if len(commit_message) > 72:
        commit_message = commit_message[:69] + "..."

    _run_git_command(['commit', '-m', commit_message])

def _get_feedback_for_iteration(solution) -> str | None:
    """Prompts the user for feedback and constructs a report for the next iteration."""
    feedback = p.ask("\n📝 Please describe the issue with the patch to help me improve it: ")
    if not feedback:
        p.warning("No feedback provided. Skipping changes.")
        return None

    return (
        f"\n\n--- Previous Attempt (Failed) ---\n"
        f"I generated the following patch, but it was incorrect.\n"
        f"Explanation:\n{solution.explanation}\n"
        f"Patch:\n{json.dumps(solution.model_dump()['changes'], indent=2)}\n"
        f"User Feedback on Failure: '{feedback}'\n"
        f"--- End of Previous Attempt ---\n"
    )

def _handle_solution_loop(request: str, context: str, slug: str, auto_apply: bool, metrics: dict) -> tuple[str, str | None]:
    """Generates and applies the solution, handling user interaction and retries."""
    p.header("5. 🧠 Generating solution...")
    current_run_history = ""
    MAX_RETRIES = 3
    patch_path = None
    final_status = "error"

    for attempt in range(MAX_RETRIES):
        if attempt > 0:
            p.info(f"\nRetrying solution... (Attempt {attempt + 1}/{MAX_RETRIES})")

        solution = phases.solve(request, context, current_run_history, tracer=metrics)

        if not solution.changes:
            p.success("\nThe agent provided an explanation without code changes:")
            p.panel(solution.explanation, title="Explanation")
            final_status = "completed (explanation only)"
            patch_path = None
            break

        patch_path = _save_patch(slug, solution)
        p.sub_info(f"Patch saved: {patch_path}")

        user_choice = 'apply' if auto_apply else preview(patch_path)

        if user_choice == 'apply':
            if not apply(patch_path):
                final_status = "applied with errors"
                break

            p.success("\nChanges have been applied to your local files.")
            confirm_commit = 'y' if auto_apply else p.ask("Test the changes. Do you want to commit them? (Y/n): ").lower()

            if confirm_commit in ('', 'y', 'yes'):
                _commit_changes(request, solution)
                final_status = "applied and committed"
                break
            
            p.warning("\nDiscarding applied changes as requested...")
            files_to_restore = list(set([change['file'] for change in solution.model_dump()['changes']]))
            _run_git_command(['restore'] + files_to_restore)

            if attempt < MAX_RETRIES - 1:
                feedback_report = _get_feedback_for_iteration(solution)
                if feedback_report:
                    current_run_history += feedback_report
                    continue
            
            final_status = "skipped (max retries)" if attempt == MAX_RETRIES - 1 else "skipped"
            break

        elif user_choice == 'skip':
            final_status = "skipped"
            break
        
        elif user_choice == 'iterate' and not auto_apply:
            if attempt < MAX_RETRIES - 1:
                p.warning("\nDiscarding proposed changes...")
                _run_git_command(['restore', '.']) # Reset any stray modifications
                feedback_report = _get_feedback_for_iteration(solution)
                if feedback_report:
                    current_run_history += feedback_report
                    continue
            
            final_status = "skipped (max retries)" if attempt == MAX_RETRIES - 1 else "skipped"
            break
        else:
            final_status = "skipped"
            break
    else: # This 'else' on the for loop is for when the loop finishes without `break`.
        final_status = "skipped (max retries)"

    return final_status, patch_path

def _finalize_run(slug: str, start_run_time: float, metrics: dict, log_entries: list[str], result_message: str):
    """Saves logs and metrics, and prints KPIs to the console."""
    end_run_time = time.time()
    metrics['end_timestamp'] = end_run_time
    metrics['total_run_duration'] = end_run_time - start_run_time
    metrics['result_message'] = result_message

    if metrics.get('prompts'):
        log_entries.append("\n\n--- Prompts Used ---")
        for phase, prompt_list in metrics['prompts'].items():
            for i, prompt_content in enumerate(prompt_list):
                log_entries.append(f"\n--- Prompt for '{phase}' (call #{i+1}) ---")
                log_entries.append(prompt_content)
                log_entries.append(f"--- End Prompt for '{phase}' (call #{i+1}) ---")
        log_entries.append("--------------------​")

    kpi_lines = [
        "\n--- KPIs ---",
        f"Total Run Time: {metrics.get('total_run_duration', 0):.2f} seconds",
        f"LLM Calls: {metrics.get('llm_calls_count', 0)}",
        f"LLM Total Duration: {metrics.get('llm_total_duration', 0):.2f} seconds",
        f"LLM Total Prompt Tokens: {metrics.get('llm_total_prompt_tokens', 0)}",
        f"LLM Total Candidates Tokens: {metrics.get('llm_total_candidates_tokens', 0)}",
        f"LLM Total Tokens: {metrics.get('llm_total_tokens', 0)}",
        f"Phase 'explore_folders' Duration: {metrics.get('phase_explore_folders_duration', 0):.2f} seconds",
        f"Phase 'select_files' Duration: {metrics.get('phase_select_files_duration', 0):.2f} seconds",
        f"Phase 'solve' Duration: {metrics.get('phase_solve_duration', 0):.2f} seconds",
        "------------"
    ]
    log_entries.extend(kpi_lines)
    log_entries.append(f"Result message: {result_message}")
    log_content = "\n".join(log_entries)
    log_path = _save_log(slug, log_content)
    metrics_path = _save_metrics(slug, metrics)

    print()
    p.panel("\n".join(kpi_lines[1:-1]), title="KPIs")
    p.success(f"\n🏁 Session finished.")
    p.sub_info(f"Log:     {log_path}")
    p.sub_info(f"Metrics: {metrics_path}")

def run_once(request: str, history: str, auto_apply=False) -> str:
    start_run_time = time.time()
    slug = _slug(request)
    log_entries = [f"Request: {request}\n"]
    metrics = {'request': request, 'start_timestamp': start_run_time}
    result_message = f"Request: '{request}' | status: unknown"

    try:
        files, context = _gather_context(request, history, metrics)

        if not files or not context:
            result_message = f"Request: '{request}' | status: skipped (no files selected)"
        else:
            final_status, patch_path = _handle_solution_loop(request, context, slug, auto_apply, metrics)
            if patch_path:
                result_message = f"Request: '{request}' | patch: {patch_path} | status: {final_status}"
            else:
                result_message = f"Request: '{request}' | status: {final_status}"

    except Exception as e:
        p.error(f"\nAn unexpected error occurred during execution: {e}")
        import traceback
        traceback.print_exc()
        log_entries.append(f"\n❌ An unexpected error occurred: {e}\n{traceback.format_exc()}")
        result_message = f"Request: '{request}' | status: error ({type(e).__name__})"
    finally:
        _finalize_run(slug, start_run_time, metrics, log_entries, result_message)

    return result_message

def main():
    os.makedirs(AGENT_DIR, exist_ok=True)
    p.wisp("Periquito the lightweight Gemini code agent is here!  (exit / quit to stop)")
    p.say("Hi!")
    p.header("")
    history = ''
    # Single-shot mode: python agent.py "request"
    if len(sys.argv) > 1:
        req = ' '.join(sys.argv[1:])
        history += run_once(req, history, auto_apply=False) + '\n'
        return

    while True:
        try:
            request = p.ask("")
        except (EOFError, KeyboardInterrupt):
            break
        if not request or request.lower() in ('exit', 'quit'):
            break
        history += run_once(request, history) + '\n'

if __name__ == '__main__':
    main()
