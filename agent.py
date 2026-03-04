#!/usr/bin/env python3
"""
agent.py  —  Dev agent with optimized context.

Usage:
    python agent.py
    python agent.py "Add dark mode support"          # non-interactive
    python -m tools.patch preview .agent/patch.json  # standalone patch preview
"""

import json, os, re, sys, io, time, subprocess
from tools import fs, phases
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
            print(result.stderr.strip(), file=sys.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing git command: {' '.join(['git'] + command)}")
        print(f"Stderr: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print("Error: 'git' command not found. Is git installed and in your PATH?")
        return False

def run_once(request: str, history: str, auto_apply=False) -> str:
    start_run_time = time.time()

    slug = _slug(request)
    result_message = ""
    log_entries = []
    metrics = {
        'request': request,
        'start_timestamp': start_run_time
    }

    log_entries.append(f"Request: {request}\n")

    try:
        protocol = fs.read_protocol()

        print("\n1. Exploring folders...")
        folders = phases.explore_folders(request, protocol, history, tracer=metrics)
        print(f"  > Folders: {', '.join(folders) if folders else 'none'}")
        print(f"  > Total tokens used: {metrics.get('llm_total_tokens', 0)}")

        print("\n2. Building file tree...")
        file_tree = fs.build_tree(folders)
        print(f"---\n{file_tree}\n---")

        print("\n3. Selecting files...")
        files = phases.select_files(request, file_tree, history, tracer=metrics)
        print(f"  > Files: {', '.join(files) if files else 'none'}")
        print(f"  > Total tokens used: {metrics.get('llm_total_tokens', 0)}")
        if not files:
            print("No files selected. Cannot proceed.")
            result_message = f"Request: '{request}' | status: skipped (no files selected)"
        else:
            print("\n4. Reading files...")
            context = phases.build_context(files)

            print("\n5. Generating solution...")
            current_run_history = "" # Start with a clean slate for solve phase
            MAX_RETRIES = 3
            final_status = "error"
            patch_path = None

            for attempt in range(MAX_RETRIES):
                if attempt > 0:
                    print(f"\n  > Retrying... (Attempt {attempt + 1}/{MAX_RETRIES})")

                solution = phases.solve(request, context, current_run_history, tracer=metrics)
                print(f"  > Total tokens used: {metrics.get('llm_total_tokens', 0)}")

                if not solution.changes:
                    print(f"\n---\n{solution.explanation}\n---")
                    final_status = "completed (explanation only)"
                    patch_path = None # Ensure patch_path is None
                    break # Exit the retry loop for explanation-only responses

                patch_path = _save_patch(slug, solution)
                print(f"\n  > Patch saved: {patch_path}")

                user_choice = 'apply' if auto_apply else preview(patch_path)

                if user_choice == 'apply':
                    ok = apply(patch_path)
                    if ok:
                        print("  > Committing changes...")
                        files_to_add = list(set([change['file'] for change in solution.model_dump()['changes']]))
                        _run_git_command(['add'] + files_to_add)

                        commit_message = f"feat: {request}"
                        if len(commit_message) > 72:
                           commit_message = commit_message[:69] + "..."

                        _run_git_command(['commit', '-m', commit_message])
                        final_status = "applied and committed"
                    else:
                        final_status = "applied with errors"
                    break
                elif user_choice == 'skip':
                    final_status = "skipped"
                    break
                elif user_choice == 'iterate' and not auto_apply:
                    if attempt < MAX_RETRIES - 1:
                        print("\nDiscarding proposed changes...")
                        _run_git_command(['restore', '.']) # Reset any stray modifications

                        feedback = input("\n📝 Please describe the issue with the patch to help me improve it: ").strip()
                        if not feedback:
                            print("No feedback provided. Skipping changes.")
                            final_status = "skipped"
                            break

                        failed_attempt_report = (
                            f"\n\n--- Previous Attempt (Failed) ---\n"
                            f"I generated the following patch, but it was incorrect.\n"
                            f"Explanation:\n{solution.explanation}\n"
                            f"Patch:\n{json.dumps(solution.model_dump()['changes'], indent=2)}\n"
                            f"User Feedback on Failure: '{feedback}'\n"
                            f"--- End of Previous Attempt ---\n"
                        )
                        current_run_history += failed_attempt_report
                        continue # Go to next iteration of the loop
                    else:
                        print("\n❌ Maximum number of retries reached.")
                        final_status = "skipped (max retries)"
                        break
                else: # Fallback or auto_apply with iterate (which we block)
                    final_status = "skipped"
                    break
            else: # This 'else' on the for loop is for when the loop finishes without `break`.
                final_status = "skipped (max retries)"

            if patch_path:
                result_message = f"Request: '{request}' | patch: {patch_path} | status: {final_status}"
            else:
                result_message = f"Request: '{request}' | status: {final_status}"

    except Exception as e:
        print(f"\n❌ An unexpected error occurred during execution: {e}")
        import traceback
        traceback.print_exc()
        log_entries.append(f"\n❌ An unexpected error occurred during execution: {e}\n")
        log_entries.append(traceback.format_exc())
        result_message = f"Request: '{request}' | status: error ({type(e).__name__})"
    finally:
        end_run_time = time.time()
        metrics['end_timestamp'] = end_run_time
        metrics['total_run_duration'] = end_run_time - start_run_time
        metrics['result_message'] = result_message # Add final message to metrics

        # Add prompts to log
        if metrics.get('prompts'):
            log_entries.append("\n\n--- Prompts Used ---")
            for phase, prompt_list in metrics['prompts'].items():
                for i, prompt_content in enumerate(prompt_list):
                    log_entries.append(f"\n--- Prompt for '{phase}' (call #{i+1}) ---")
                    log_entries.append(prompt_content)
                    log_entries.append(f"--- End Prompt for '{phase}' (call #{i+1}) ---")
            log_entries.append("--------------------​")

        # Format and append KPIs to log_entries and print
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
        _save_log(slug, log_content)

        print("\n".join(kpi_lines))
        print(f"\n> Session finished.")
        print(f"> Log:   {AGENT_DIR}/{slug}.txt")
        _save_metrics(slug, metrics)
        print(f"> Metrics: {AGENT_DIR}/{slug}_metrics.json")

    return result_message

def main():
    os.makedirs(AGENT_DIR, exist_ok=True)
    print("🤖 Dev Agent ready.  (exit / quit to stop)\n")

    history = ''
    # Single-shot mode: python agent.py "request"
    if len(sys.argv) > 1:
        req = ' '.join(sys.argv[1:])
        history += run_once(req, history, auto_apply=False) + '\n'
        return

    while True:
        try:
            request = input("👉 ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not request or request.lower() in ('exit', 'quit'):
            break
        history += run_once(request, history) + '\n'

if __name__ == '__main__':
    main()
