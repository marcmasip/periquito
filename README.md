# 🦖 Periquito Agent

A minimalist, command-line Gemini AI coding agent. 
It analyzes a codebase, understands requests, and generates reviewable code patches.


<img src="https://azestudio.net/img/periquito_cli.png" width="400"> <img src="https://azestudio.net/img/periquito_cli2.png" width="570">

## Usage

**Interactive Mode:**
```bash
python src/agent.py
```

**Non-interactive Mode:**
```bash
python src/agent.py "Your coding request here"
```

## How It Works

The agent's effectiveness relies on understanding the project structure. It uses the `README.md` for a high-level description and a list of key folders to start its analysis.

For best results, your project `README.md` should contain a concise description and a `# Project Structure` section.

**Example:**
```markdown
# My Awesome Project

This project does X by using Y and Z.

# Project Structure
- `src`: Main application source code.
- `docs`: Project documentation.
- `tests`: Unit and integration tests.
```

The agent uses this context to perform its task:
1.  **Explore:** Identifies relevant folders based on the request and project structure.
2.  **Select:** Narrows down to specific files within those folders.
3.  **Solve:** Reads the files and generates a code patch to fulfill the request.
4.  **Review:** You can `apply`, `iterate` on, or `skip` the proposed patch.

## Tools

**Patch Preview:**
To review a previously generated patch:
```bash
python src/agent.py patch preview .agent/patch.json
```

## The `.agent` Directory

This directory stores run artifacts:
- `*.json`: Generated patch files.
- `*_metrics.json`: Performance metrics.
- `*.txt`: Full logs and prompts.

## Project Structure
- `src`: Core agent logic and tools.
