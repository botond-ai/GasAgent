import sys
import subprocess

result = subprocess.run(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "9000"],
    cwd="c:\\xampp\\htdocs\\ai-agents-hu\\mini_projects\\szekeres.aurel\\meetingai",
    capture_output=True,
    text=True,
    timeout=30,
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print("\nReturn code:", result.returncode)
