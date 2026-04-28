import sys

_REPLACEMENTS = {
    "✅": "[OK]",
    "❌": "[ERROR]",
    "🚀": "[INFO]",
    "⚠️": "[WARN]",
    "⚠": "[WARN]",
    "ℹ️": "[INFO]",
    "ℹ": "[INFO]",
    "🎉": "[DONE]",
    "📂": "[DIR]",
    "📋": "[FILE]",
    "🔄": "[SYNC]",
    "🔍": "[SCAN]",
}


def safe_text(value: object) -> str:
    text = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    for source, target in _REPLACEMENTS.items():
        text = text.replace(source, target)
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def safe_print(*values: object, sep: str = " ", end: str = "\n", flush: bool = False) -> None:
    text = sep.join(safe_text(value) for value in values)
    print(text, end=end, flush=flush)
