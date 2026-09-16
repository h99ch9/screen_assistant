"""Run the maintained pytest suite with a nonzero exit on any failure."""
from pathlib import Path
import os
import sys


def main(argv=None):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        import pytest
    except ModuleNotFoundError:
        print("Install test dependencies: uv sync --locked --extra test", file=sys.stderr)
        return 2
    print(f"Qt test platform: {os.environ['QT_QPA_PLATFORM']}; tests use a fake Ollama server.")
    print("Live desktop appearance and real-model accuracy require separate manual checks.")
    args = [str(Path(__file__).with_name("test_verification.py")), "-v"]
    return pytest.main(args + (list(argv) if argv is not None else sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
