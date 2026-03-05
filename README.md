# 🐦 Periquito

_Your small but mighty (pequeño pero matón) coding assistant!_

Periquito is a lightweight, command-line AI coding agent designed to help you with your development tasks. It analyzes your codebase, understands your requests in natural language, and generates code patches that you can review and apply.

## ✨ Features

- **Optimized Context:** Intelligently selects relevant files and folders to provide the LLM with the right context, saving tokens and improving accuracy.
- **Interactive Workflow:** Preview generated changes before applying them. You can apply, skip, or provide feedback for another attempt.
- **Git Integration:** Automatically commits applied changes with a conventional commit message.
- **Multi-phase Tasks:** Can chain requests together for more complex tasks.
- **Detailed Logging:** Saves logs, metrics, and generated patches in the `.agent` directory for full transparency.
- **Interactive & Non-interactive modes:** Run it in a conversational loop or as a single-shot command.

## 🚀 Usage

### Interactive Mode

To start a conversation with Periquito, simply run:
```bash
python agent.py
```
Then, type your request at the prompt.

### Non-interactive (Single-shot) Mode

For quick tasks, you can pass the request directly as an argument:
```bash
python agent.py "Your coding request here"
```

### Standalone Patch Preview

If you want to review a patch later, you can use the patch tool:
```bash
python -m tools.patch preview .agent/patch.json
```

## ⚙️ How It Works

1.  **Context Gathering:** Periquito scans your project structure (guided by a `.protocol` file if available) and the user request to identify the most relevant files.
2.  **Solving:** It builds a context prompt with the selected file contents and sends it to the language model to generate a solution in the form of a JSON patch.
3.  **User Interaction:** The proposed patch is presented to you. You can choose to:
    - `apply`: Apply the changes to your local files and commit them.
    - `iterate`: Provide feedback and ask Periquito to try again.
    - `skip`: Discard the proposed changes.

## 📁 The `.agent` Directory

This directory is created automatically to store all artifacts from Periquito's runs:

- `*.json`: The generated patch files.
- `*_metrics.json`: Detailed metrics for each run (timing, token counts, etc.).
- `*.txt`: Full logs, including the prompts used.