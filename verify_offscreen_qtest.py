"""Compatibility entry point for the maintained foundation Qt tests."""
from screen_assistant.verify import main

if __name__ == "__main__":
    raise SystemExit(main(["-k", "foundation"]))
