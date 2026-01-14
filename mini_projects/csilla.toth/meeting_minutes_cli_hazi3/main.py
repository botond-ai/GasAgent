import sys
import subprocess
import os
from pathlib import Path


VENV_DIR = Path(".venv")
REQUIREMENTS_FILE = Path("requirements.txt")


def is_running_in_venv() -> bool:
    return sys.prefix != sys.base_prefix


def venv_python_path() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def create_venv():
    print("🐍 Virtuális környezet létrehozása (.venv)...")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    print("✅ venv létrehozva.")


def install_requirements(python_executable: Path):
    if not REQUIREMENTS_FILE.exists():
        print("⚠️ requirements.txt nem található, telepítés kihagyva.")
        return

    print("📦 Dependency-k telepítése...")
    subprocess.check_call(
        [str(python_executable), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)]
    )
    print("✅ Dependency-k telepítve.")


def restart_with_venv(python_executable: Path):
    print("🔁 Újraindítás a virtuális környezetből...\n")
    subprocess.check_call(
        [str(python_executable), __file__] + sys.argv[1:]
    )
    sys.exit(0)


def bootstrap_venv_if_needed():
    if is_running_in_venv():
        return

    if not VENV_DIR.exists():
        create_venv()
        python_exec = venv_python_path()
        install_requirements(python_exec)
        restart_with_venv(python_exec)

    # venv már létezik, de nem onnan futunk
    python_exec = venv_python_path()
    restart_with_venv(python_exec)


def main():
    bootstrap_venv_if_needed()

    # innentől biztosan a venv Python fut
    from cli.app import MeetingMinutesApp

    print("Adj meg egy meeting jegyzet szöveget (ENTER, majd Ctrl+D / Ctrl+Z):\n")

    try:
        text = ""
        while True:
            text += input() + "\n"
    except EOFError:
        pass

    app = MeetingMinutesApp()
    app.run(text)


if __name__ == "__main__":
    main()
