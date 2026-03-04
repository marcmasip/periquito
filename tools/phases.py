from pydantic import BaseModel, Field
from typing import List, Dict
from . import llm, fs
import time

# --- Data Models ---

class FolderList(BaseModel):
    folders: List[str] = Field(description="List of folder paths relevant to the user's request. Should include './' for root-level files.")

class FileList(BaseModel):
    files: List[str] = Field(description="List of file paths relevant for generating the solution.")

class Change(BaseModel):
    file: str
    search: str
    replace: str

class Solution(BaseModel):
    explanation: str = Field(description="Detailed, step-by-step explanation of the changes.")
    changes: List[Change] = Field(description="List of search/replace blocks for code modification.")

# --- Prompts ---

EXPLORE_PROMPT = """
Your goal is to identify the most relevant folders to inspect based on the user's request and a summary of the project structure.
This helps to focus the search and avoid analyzing the entire project. Pay attention to documentation files like READMEs if they are listed.
Your response must be a selection of paths from the 'Project Structure Summary' below. Do not invent paths.

User Request: {request}

Project Structure Summary:
---
{protocol}
---

History of previous interactions:
---
{history}
---

Respond with a JSON object containing a 'folders' key with a list of folder paths.
"""

SELECT_PROMPT = """
From the file tree of the relevant folders selected previously, your task is to pinpoint the exact files needed to solve the user's request.
Select the minimum set of files required to read and understand the existing code before proposing changes.

User Request: {request}

File Tree of Relevant Folders:
---
{file_tree}
---

History of previous interactions:
---
{history}
---

Respond with a JSON object containing a 'files' key with a list of file paths.
"""

SOLVE_PROMPT = """
You are a Senior proficient software engineer. Your task is to solve the user's request based on the provided context.
Provide a detailed explanation of your solution and a code patch in JSON format.
The JSON patch should contain a list of changes, each with 'file', 'search', and 'replace' keys.
'search' must be an exact match of the code to be replaced. If it's a new file, 'search' should be an empty string.
'replace' is the new code.

User Request: {request}

Context (selected file contents):
---
{context}
---

History of previous interactions:
---
{history}
---

Respond with a single JSON object containing 'explanation' and 'changes'.
"""

# --- Phases ---

def explore_folders(request: str, protocol: str, history: str, tracer: dict = None) -> List[str]:
    start_time = time.time()
    prompt = EXPLORE_PROMPT.format(request=request, protocol=protocol, history=history or 'None')
    result = llm.generate_json(prompt, FolderList, tracer=tracer, phase_name="explore_folders", model_name=llm.MODEL_NAME_DEFAULT)
    end_time = time.time()
    if tracer is not None:
        tracer['phase_explore_folders_duration'] = tracer.get('phase_explore_folders_duration', 0.0) + (end_time - start_time)
    return result.folders

def select_files(request: str, file_tree: str, history:str, tracer: dict = None) -> List[str]:
    start_time = time.time()
    prompt = SELECT_PROMPT.format(request=request, file_tree=file_tree, history=history or 'None')
    result = llm.generate_json(prompt, FileList, tracer=tracer, phase_name="select_files", model_name=llm.MODEL_NAME_DEFAULT)
    end_time = time.time()
    if tracer is not None:
        tracer['phase_select_files_duration'] = tracer.get('phase_select_files_duration', 0.0) + (end_time - start_time)
    return result.files

def build_context(files: List[str]) -> str:
    return fs.read_files_as_context(files)

def solve(request: str, context: str, history: str, tracer: dict = None) -> Solution:
    start_time = time.time()
    prompt = SOLVE_PROMPT.format(request=request, context=context, history=history or 'None')
    result = llm.generate_json(prompt, Solution, tracer=tracer, model_name=llm.MODEL_NAME_ADVANCED, phase_name="solve")
    end_time = time.time()
    if tracer is not None:
        tracer['phase_solve_duration'] = tracer.get('phase_solve_duration', 0.0) + (end_time - start_time)
    return result
