#!/usr/bin/env python3
"""
agent.py  —  Dev agent with optimized context.

Usage:
    python agent.py
    python agent.py "Add dark mode support"          # non-interactive
    python -m tools.patch preview .agent/patch.json  # standalone patch preview
"""

import json, os, re, sys, io, time
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
        readme = fs.read_readme()

        print("\n🔎 Step 1: Exploring folders...")
        folders = phases.explore_folders(request, readme, history, tracer=metrics)
        print(f"📂 Folders to inspect: {', '.join(folders) if folders else 'none'}")
        print(f"✨ Tokens used so far: {metrics.get('llm_total_tokens', 0)}")

        print("\n🌳 Step 2: Building file tree for selected folders...")
        file_tree = fs.build_tree(folders)
        print("File tree:\n---")
        print(file_tree)
        print("---\n")

        print("📄 Step 3: Selecting specific files to read...")
        files = phases.select_files(request, file_tree, history, tracer=metrics)
        print(f"📝 Files to read: {', '.join(files) if files else 'none'}")
        print(f"✨ Tokens used so far: {metrics.get('llm_total_tokens', 0)}")
        if not files:
            print("No files selected. Cannot proceed.")
            result_message = f"Request: '{request}' | status: skipped (no files selected)"
        else:
            print("\n📚 Step 4: Building context from selected files...")
            context = phases.build_context(files)

            print("\n💡 Step 5: Generating solution...")
            current_run_history = history
            MAX_RETRIES = 3
            final_status = "error"
            patch_path = None

            for attempt in range(MAX_RETRIES):
                if attempt > 0:
                    print(f"\n🔄 Retrying generation (Attempt {attempt + 1}/{MAX_RETRIES})...")

                solution = phases.solve(request, context, current_run_history, tracer=metrics)
                print(f"✨ Tokens used so far: {metrics.get('llm_total_tokens', 0)}")

                if not solution.changes:
                    print("\n--- Agent's Response ---")
                    print(solution.explanation)
                    print("------------------------")
                    final_status = "completed (explanation only)"
                    patch_path = None # Ensure patch_path is None
                    break # Exit the retry loop for explanation-only responses

                patch_path = _save_patch(slug, solution)
                print(f"\n💾 Patch saved → {patch_path}")

                user_choice = 'apply' if auto_apply else preview(patch_path)

                if user_choice == 'apply':
                    ok = apply(patch_path)
                    final_status = "applied" if ok else "applied with errors"
                    break
                elif user_choice == 'skip':
                    final_status = "skipped"
                    break
                elif user_choice == 'retry' and not auto_apply:
                    if attempt < MAX_RETRIES - 1:
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
                else: # Fallback or auto_apply with retry (which we block)
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
        print(f"📝 Session finish") # This message goes to the original stdout
        print(f"📝 Raw interaction log saved → {AGENT_DIR}/{slug}.txt")
        _save_metrics(slug, metrics)
        print(f"📝 Metrics saved → {AGENT_DIR}/{slug}_metrics.json")

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
