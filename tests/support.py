"""Small host build helpers; never select PSP, firmware or mounted-device inputs."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
C_TESTS = TESTS / "c"


def temporary_directory():
    directory = ROOT / "build/tests"
    directory.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=directory)


def compile_program(output, *sources, includes=(), defines=(), flags=()):
    command = [os.environ.get("CC", "cc"), "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror"]
    command += list(flags)
    if os.environ.get("TEST_SANITIZE") == "1":
        command += ["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    for directory in includes:
        command += ["-I", str(directory)]
    command += [f"-D{value}" for value in defines]
    command += [str(source) for source in sources]
    subprocess.run(command + ["-o", str(output)], check=True)


def run_program(binary, *arguments):
    environment = os.environ.copy()
    if environment.get("TEST_SANITIZE") == "1":
        environment["UBSAN_OPTIONS"] = "halt_on_error=1"
        if sys.platform == "darwin":
            environment["ASAN_OPTIONS"] = "detect_leaks=0"
    subprocess.run([str(binary), *map(str, arguments)], check=True, env=environment)


def compile_library(output, *sources):
    # ctypes loads into an ordinary Python process, not an ASan executable.
    # Sanitizer coverage belongs to standalone C harnesses using compile_program.
    subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-O2", "-Wall", "-Wextra",
                    "-Werror", "-shared", "-fPIC", *map(str, sources), "-o", str(output)], check=True)
