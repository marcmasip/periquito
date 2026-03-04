import os
import json
import time # Added for timing LLM calls
import sys # Added for logging to stderr
import google.generativeai as genai
from pydantic import BaseModel

# Configure the API key
try:
    # It's recommended to use an environment variable for the API key.
    # For example: export GEMINI_API_KEY="your_api_key"
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("🚨 GEMINI_API_KEY environment variable not set.", file=sys.stderr)
    print("Please set it to your Google AI Studio API key.", file=sys.stderr)
    exit(1)

MODEL_NAME_DEFAULT = "gemini-2.5-flash"
MODEL_NAME_ADVANCED = "gemini-2.5-pro"

def _log_llm_progress(phase_name: str, duration: float, prompt_tokens: int, candidates_tokens: int, total_tokens: int):
    """Logs LLM call details to stderr."""
    print(
        f"  [LLM Call for {phase_name}] "
        f"Duration: {duration:.2f}s | "
        f"Prompt Tokens: {prompt_tokens} | "
        f"Candidate Tokens: {candidates_tokens} | "
        f"Total Tokens: {total_tokens}",
        file=sys.stderr
    )

def generate_json(prompt: str, pydantic_model: BaseModel, tracer: dict = None, model_name: str = MODEL_NAME_DEFAULT, phase_name: str = "Unknown") -> BaseModel:
    """
    Generates a response from the LLM in JSON format and parses it using a Pydantic model.
    """
    print(f"  Making LLM call for '{phase_name}' using model '{model_name}'...", file=sys.stderr)
    model = genai.GenerativeModel(
        model_name,
        generation_config={"response_mime_type": "application/json"},
        system_instruction=f"You are a helpful assistant. Respond in JSON format that adheres to this Pydantic schema: {pydantic_model.model_json_schema()}"
    )

    start_time = time.time()
    try:
        response = model.generate_content(prompt)
        end_time = time.time()
        duration = end_time - start_time

        prompt_tokens = 0
        candidates_tokens = 0
        total_tokens = 0

        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count
            candidates_tokens = response.usage_metadata.candidates_token_count
            total_tokens = prompt_tokens + candidates_tokens

            _log_llm_progress(phase_name, duration, prompt_tokens, candidates_tokens, total_tokens)

            if tracer is not None:
                tracer['llm_calls_count'] = tracer.get('llm_calls_count', 0) + 1
                tracer['llm_total_duration'] = tracer.get('llm_total_duration', 0.0) + duration
                tracer['llm_total_prompt_tokens'] = tracer.get('llm_total_prompt_tokens', 0) + prompt_tokens
                tracer['llm_total_candidates_tokens'] = tracer.get('llm_total_candidates_tokens', 0) + candidates_tokens
                tracer['llm_total_tokens'] = tracer.get('llm_total_tokens', 0) + total_tokens
        else:
            print(f"  [LLM Call for {phase_name}] No usage metadata available. Duration: {duration:.2f}s", file=sys.stderr)
            if tracer is not None:
                tracer['llm_calls_count'] = tracer.get('llm_calls_count', 0) + 1
                tracer['llm_total_duration'] = tracer.get('llm_total_duration', 0.0) + duration

        response_json = json.loads(response.text)
        return pydantic_model.model_validate(response_json)
    except (json.JSONDecodeError, ValueError) as e:
        end_time = time.time()
        duration = end_time - start_time
        if tracer is not None:
            tracer['llm_calls_count'] = tracer.get('llm_calls_count', 0) + 1
            tracer['llm_total_duration'] = tracer.get('llm_total_duration', 0.0) + duration
        print(f"Error: Failed to decode LLM response as JSON for '{phase_name}'. Error: {e}", file=sys.stderr)
        print(f"Raw response:\n---\n{response.text}\n---", file=sys.stderr)
        raise ValueError("LLM did not return valid JSON.") from e
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        if tracer is not None:
            tracer['llm_calls_count'] = tracer.get('llm_calls_count', 0) + 1
            tracer['llm_total_duration'] = tracer.get('llm_total_duration', 0.0) + duration
        print(f"An unexpected error occurred during LLM generation for '{phase_name}': {e}", file=sys.stderr)
        try:
            print(f"Prompt feedback: {response.prompt_feedback}", file=sys.stderr)
        except Exception:
            pass
        raise
