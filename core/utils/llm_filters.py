import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import re

def remove_repeating_substrings(s: str) -> str:
    """
    Remove any substring (length 1 or more) that repeats more than 3 times consecutively,
    but do not remove repeating substrings that are only brackets or braces (e.g., '}', ']', '}}', ']]', etc.).
    For each possible substring length (up to half the string), replace >3 consecutive repeats with 3,
    unless the substring is only made of brackets/braces.
    """
    brackets = set("[]{}")
    max_len = len(s) // 2
    for l in range(1, max_len + 1):
        # Skip substrings that are only brackets/braces
        def is_bracket_only(sub):
            return all(c in brackets for c in sub)
        pattern = re.compile(r"((.{%d}))\1{3,}" % l, re.DOTALL)
        while True:
            def repl(m):
                sub = m.group(1)
                if is_bracket_only(sub):
                    return m.group(0)
                return sub * 3
            new_s = pattern.sub(repl, s)
            if new_s == s:
                break
            s = new_s
    return s

def format_yaml_prompt(
    yaml_file: str,
    sections: Dict[str, str],
    additional_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format a YAML prompt using modular sections and dynamic headers.

    Args:
        yaml_file (str): Path to the YAML file containing the prompt template.
        sections (Dict[str, str]): Dictionary of section contents to inject into the template.
        additional_context (Dict[str, Any]): Additional context variables for formatting.

    Returns:
        str: Formatted prompt string.
    """
    prompt_path = Path(yaml_file)
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {yaml_file}")

    # Load YAML content
    yaml_content = yaml.safe_load(prompt_path.read_text())

    # Extract template and system prompt
    template = yaml_content.get("template", "")
    system_prompt = yaml_content.get("system", "")

    # Format sections (no headers, just content)
    formatted_sections = {
        key: content.strip()
        for key, content in sections.items()
        if content and content.strip()
    }

    # Add additional context variables
    if additional_context:
        formatted_sections.update(additional_context)

    # Render the final prompt
    return template.format(**formatted_sections, system=system_prompt)

if __name__ == "__main__":
    # Strictly for testing
    to_filter = """This is a test string that contains repeating substrings. This is a test string that contains repeating substrings. This is a test string that contains repeating substrings. This is a test string that contains repeating substrings. 
    HGelol HGelol HGelol HGelol HGelol HGelol HGelol HGelol
    fopiezbfe"""
    filtered = remove_repeating_substrings(to_filter)
    with open("filtered_output.txt", "w", encoding="utf-8") as f:
        f.write(filtered.encode('utf-8', errors='ignore').decode('utf-8'))