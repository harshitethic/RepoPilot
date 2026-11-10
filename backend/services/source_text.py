"""Physical source lines matching editor and Git line numbers."""
import re

def source_lines(text: str) -> list[str]:
    if not text:
        return []
    lines = re.split(r"\r\n|\r|\n", text)
    if lines[-1] == "":
        lines.pop()
    return lines
