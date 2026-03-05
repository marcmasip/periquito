import sys
import time
from threading import Event

# ANSI escape codes for colors
class Ansi:
    """ANSI color codes and styles"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Basic colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    DARK_GRAY = "\033[90m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    
    # Bright/light colors
    BRIGHT_BLACK = "\033[90m" # Grey
    BRIGHT_MAGENTA = "\033[95m"

def _colored_print(emoji: str, color: str, message: str, **kwargs):
    """Generic print function with emoji and color."""
    print(f"{emoji} {color}{message}{Ansi.RESET}", **kwargs)

def say(message: str, **kwargs):
    """Prints a message from the agent"""
    print(f"\n🦜  {Ansi.DARK_GRAY}__/{Ansi.RESET}  {Ansi.BOLD}{message}{Ansi.RESET} {Ansi.DARK_GRAY}/{Ansi.RESET} ", **kwargs)

def wisp(message: str, **kwargs):
    """Prints whisp"""
    print(f"\n{Ansi.DARK_GRAY}{message}{Ansi.RESET} ", **kwargs)
	
def header(message: str, **kwargs):
    """Prints a bold, bright magenta header."""
    print(f"\n{Ansi.BOLD}{Ansi.BRIGHT_MAGENTA}{message}{Ansi.RESET}", **kwargs)

def info(message: str, **kwargs):
    """Prints an informational message in blue."""
    _colored_print("ℹ️ ", Ansi.BLUE, message, **kwargs)

def sub_info(message: str, **kwargs):
    """Prints a sub-informational message, indented."""
    print(f"  {Ansi.DARK_GRAY}> {message}{Ansi.RESET}", **kwargs)

def success(message:str, **kwargs):
    """Prints a success message in green."""
    _colored_print("✅", Ansi.GREEN, message, **kwargs)

def warning(message: str, **kwargs):
    """Prints a warning message in yellow."""
    _colored_print("⚠️ ", Ansi.YELLOW, message, **kwargs)

def error(message: str, **kwargs):
    """Prints an error message in red to stderr."""
    _colored_print("❌", Ansi.RED, message, file=sys.stderr, **kwargs)

def ask(prompt: str) -> str:
    """Prints a prompt for user input and returns the response."""
    return input(f"👉 {Ansi.CYAN}{prompt}{Ansi.RESET}").strip()

def progress_bar_runner(stop_event: Event, model_name: str = "...", prompt_len: int = 0, width: int = 40, duration: int = 60):
    """
    Displays and updates a progress bar that loops.
    To be run in a separate thread.
    """
    spinners = ['/', '-', '\\', '|']
    i = 0
    start_time = time.time()
    while not stop_event.is_set():
        elapsed = (time.time() - start_time)
        progress = (elapsed % duration) / duration
        
        filled_length = int(width * progress)
        bar = '█' * filled_length + '-' * (width - filled_length)
        
        spinner = spinners[i % len(spinners)]
        i += 1
        
        # Format prompt length to be more readable
        if prompt_len > 1000:
            prompt_len_str = f"{prompt_len/1000:.1f}k"
        else:
            prompt_len_str = str(prompt_len)

        info_text = f"{Ansi.DARK_GRAY}({model_name}, {prompt_len_str} chars){Ansi.RESET}"
        sys.stdout.write(f"\r  > Pensando... {info_text} {spinner} [{bar}]")
        sys.stdout.flush()
        
        time.sleep(0.1)
    
    # Clear the progress bar line
    sys.stdout.write('\r' + ' ' * (width + 80) + '\r')
    sys.stdout.flush()

def panel(content: str, title: str = "", border_color: str = Ansi.BRIGHT_BLACK, **kwargs):
    """Prints content inside a colored panel."""
    top_border = f"--- {title} ---" if title else "---"
    print(f"{border_color}{top_border}{Ansi.RESET}", **kwargs)
    
    print(content, **kwargs)
    
    bottom_border = f"--- End {title} ---" if title else "---"
    print(f"{border_color}{bottom_border}{Ansi.RESET}", **kwargs)
