from pydantic import BaseModel, Field
from typing import List, Dict
from . import llm, fs
from .config import settings
import time

# --- Data Models ---

class FolderList(BaseModel):
    folders: List[str] = Field(description="List of folder paths relevant to the user's request. Should include './' for root-level files.")

class FileList(BaseModel):
    files: List[str] = Field(description="List of file paths relevant for generating the solution. Must be exact paths from the file tree.")

class Change(BaseModel):
    file: str
    search: str
    replace: str

class Solution(BaseModel):
    explanation: str = Field(description="Detailed, step-by-step explanation of the changes.")
    changes: List[Change] = Field(description="List of search/replace blocks for code modification.")
    request_files: List[str] | None = Field(default=None, description="Optional list of additional file paths to load in the next iteration if the current context is insufficient.")
    next_phase_instructions: str | None = Field(default=None, description="Optional instructions for a subsequent phase if the task requires multiple steps.")

# --- Prompts ---

def _load_prompt_template(template_path: str) -> str:
    """Loads a prompt template from a file."""
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except (IOError, FileNotFoundError) as e:
        raise ValueError(f"Could not load prompt template from '{template_path}'. "
                         f"Please ensure the file exists and the path in 'config.json' is correct. "
                         f"Error: {e}")

# Load prompts from files specified in config
EXPLORE_PROMPT = _load_prompt_template(settings.prompt_templates['explore'])
SELECT_PROMPT = _load_prompt_template(settings.prompt_templates['select'])
SOLVE_PROMPT = _load_prompt_template(settings.prompt_templates['solve'])

# --- Phases ---

def explore_folders(request: str, protocol: str, history: str, tracer: dict = None) -> List[str]:
    start_time = time.time()
    prompt = EXPLORE_PROMPT.format(request=request, protocol=protocol, history=history or 'None')
    result = llm.generate_json(prompt, FolderList, tracer=tracer, phase_name="explore_folders", model_name=llm.MODEL_NAME_DEFAULT)
    end_time = time.time()
    if tracer is not None:
        tracer['kpi.explore_folders.duration_ms'] = (end_time - start_time) * 1000
    return result.folders

def select_files(request: str, file_tree: str, history:str, tracer: dict = None) -> List[str]:
    start_time = time.time()
    prompt = SELECT_PROMPT.format(request=request, file_tree=file_tree, history=history or 'None')
    result = llm.generate_json(prompt, FileList, tracer=tracer, phase_name="select_files", model_name=llm.MODEL_NAME_DEFAULT)
    end_time = time.time()
    if tracer is not None:
        tracer['kpi.select_files.duration_ms'] = (end_time - start_time) * 1000
    return result.files

def build_context(files: List[str]) -> str:
    return fs.read_files_as_context(files)

def solve(request: str, context: str, history: str, tracer: dict = None) -> Solution:
    start_time = time.time()
    prompt = SOLVE_PROMPT.format(request=request, context=context, history=history or 'None')
    result = llm.generate_json(prompt, Solution, tracer=tracer, model_name=llm.MODEL_NAME_ADVANCED, phase_name="solve")
    end_time = time.time()
    if tracer is not None:
        tracer['kpi.solve.duration_ms'] = (end_time - start_time) * 1000
    return result
