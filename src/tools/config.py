import json
import os
from types import SimpleNamespace

def _load_config():
    """Loads configuration from config.json, providing defaults."""
    config_path = 'config.json'
    
    # Default settings
    config_data = {
        "agent_dir": ".agent",
        "max_retries": 5,
        "commit_message_prefix": "feat: ",
        "small_project_threshold_lines": 150,
        "large_file_tree_threshold_lines": 200,
        "prompt_templates": {
            "explore": "src/template/explore.txt",
            "select": "src/template/select.txt",
            "solve": "src/template/solve.txt"
        }
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Recursively update nested dictionaries
                for key, value in user_config.items():
                    if isinstance(value, dict) and isinstance(config_data.get(key), dict):
                        config_data[key].update(value)
                    else:
                        config_data[key] = value
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load or parse config.json. Using default settings. Error: {e}")

    # Resolve template paths to be relative to the project root, so it works when imported
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if 'prompt_templates' in config_data and isinstance(config_data['prompt_templates'], dict):
        for key, template_path in config_data['prompt_templates'].items():
            if isinstance(template_path, str) and not os.path.isabs(template_path):
                config_data['prompt_templates'][key] = os.path.join(project_root, template_path)

    return SimpleNamespace(**config_data)

# Load config once on module import
settings = _load_config()
