import os
import json
import time
import sys
import threading
from google import genai
from google.genai import types
from pydantic import BaseModel
from . import print as printer


# 1. Instanciación del Cliente
try:
    # El cliente busca automáticamente GEMINI_API_KEY en las variables de entorno,
    # pero podemos pasarla explícitamente para mantener tu lógica.
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("🚨 GEMINI_API_KEY environment variable not set.", file=sys.stderr)
    print("Please set it to your Google AI Studio API key.", file=sys.stderr)
    exit(1)

MODEL_NAME_DEFAULT = "gemini-2.5-flash"
MODEL_NAME_ADVANCED = "gemini-2.5-pro"

# Nota: _MODEL_CACHE y _get_model han sido eliminados.
# En la nueva SDK no necesitas instanciar clases "GenerativeModel" con estado;
# simplemente pasas la configuración en la llamada al cliente.

def _log_llm_progress(phase_name: str, model_name: str, duration: float, prompt_tokens: int, candidates_tokens: int, total_tokens: int):
    """Logs LLM call details to stdout."""
    print(
        f"  > LLM '{phase_name}' ({model_name}): {duration:.2f}s, {total_tokens} tokens",
        file=sys.stdout
    )

def generate_json(prompt: str, pydantic_model: type[BaseModel], tracer: dict = None, model_name: str = MODEL_NAME_DEFAULT, phase_name: str = "Unknown") -> BaseModel:
    """
    Generates a response from the LLM in JSON format and parses it using a Pydantic model.
    """
    if tracer is not None:
        if 'prompts' not in tracer:
            tracer['prompts'] = {}
        if phase_name not in tracer['prompts']:
            tracer['prompts'][phase_name] = []
        tracer['prompts'][phase_name].append(prompt)

    # 2. Configuración nativa de Pydantic
    config = types.GenerateContentConfig(
        system_instruction="You are a helpful assistant.",
        response_mime_type="application/json",
        response_schema=pydantic_model, # ¡La nueva SDK soporta Pydantic de forma nativa!
    )

    start_time = time.time()
    try:
        # 3. Llamada mediante client.models
        stop_event = threading.Event()
        progress_thread = threading.Thread(
            target=printer.progress_bar_runner, 
            args=(stop_event, model_name, len(prompt))
        )
        progress_thread.start()

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
        finally:
            stop_event.set()
            progress_thread.join()

        end_time = time.time()
        duration = end_time - start_time

        prompt_tokens = 0
        candidates_tokens = 0
        total_tokens = 0

        # 4. Extracción de metadatos (la estructura es casi idéntica, pero bajo types)
        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count
            candidates_tokens = response.usage_metadata.candidates_token_count
            total_tokens = prompt_tokens + candidates_tokens

            _log_llm_progress(phase_name, model_name, duration, prompt_tokens, candidates_tokens, total_tokens)

            if tracer is not None:
                tracer['llm_calls_count'] = tracer.get('llm_calls_count', 0) + 1
                tracer['llm_total_duration'] = tracer.get('llm_total_duration', 0.0) + duration
                tracer['llm_total_prompt_tokens'] = tracer.get('llm_total_prompt_tokens', 0) + prompt_tokens
                tracer['llm_total_candidates_tokens'] = tracer.get('llm_total_candidates_tokens', 0) + candidates_tokens
                tracer['llm_total_tokens'] = tracer.get('llm_total_tokens', 0) + total_tokens
        else:
            print(f"  > LLM '{phase_name}' ({model_name}): {duration:.2f}s (no token usage metadata)", file=sys.stdout)
            if tracer is not None:
                tracer['llm_calls_count'] = tracer.get('llm_calls_count', 0) + 1
                tracer['llm_total_duration'] = tracer.get('llm_total_duration', 0.0) + duration

        # Parseo directo usando las capacidades de Pydantic V2
        return pydantic_model.model_validate_json(response.text)

    except (json.JSONDecodeError, ValueError) as e:
        end_time = time.time()
        duration = end_time - start_time
        if tracer is not None:
            tracer['llm_calls_count'] = tracer.get('llm_calls_count', 0) + 1
            tracer['llm_total_duration'] = tracer.get('llm_total_duration', 0.0) + duration
        print(f"Error: Failed to decode LLM response as JSON for '{phase_name}'. Error: {e}", file=sys.stderr)
        
        # Extracción segura en caso de que falle la generación completa
        raw_text = response.text if hasattr(response, 'text') else "No text returned"
        print(f"Raw response:\n---\n{raw_text}\n---", file=sys.stderr)
        raise ValueError("LLM did not return valid JSON.") from e
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        if tracer is not None:
            tracer['llm_calls_count'] = tracer.get('llm_calls_count', 0) + 1
            tracer['llm_total_duration'] = tracer.get('llm_total_duration', 0.0) + duration
        print(f"An unexpected error occurred during LLM generation for '{phase_name}': {e}", file=sys.stderr)
        raise