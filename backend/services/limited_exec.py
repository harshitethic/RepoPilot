"""Isolated POSIX child launcher.

Executed in a fresh Python interpreter before execve of Git. Avoids using
preexec_fn in the multi-threaded FastAPI process.
"""
import os
import platform
import resource
import sys


def main():
    cpu_seconds, memory_bytes, max_file_bytes = map(int, sys.argv[1:4])
    argv = sys.argv[4:]
    if not argv:
        raise SystemExit(2)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    # macOS limits are frequently inherited with a zero RLIMIT_AS hard cap;
    # a requested finite value then makes even benign Git launches fail.
    # Only Linux uses verified RLIMIT_AS enforcement here.
    if platform.system() == "Linux":
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_bytes, max_file_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.execvpe(argv[0], argv, os.environ)


if __name__ == "__main__":
    main()
