import sys
from pathlib import Path
import shutil
import os

def python_cmd():
    if not getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        if exe.name.lower() not in {"installer.exe", "instalador.exe"}:
            return [str(exe)]

    for name in ("python", "python3"):
        found = shutil.which(name)
        if found:
            return [found]

    py = shutil.which("py")
    if py:
        return [py, "-3"]

    for base in (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python",
        Path(r"C:\Python311"),
        Path(r"C:\Python312"),
        Path(r"C:\Python313"),
        Path(r"C:\Python314"),
    ):
        if not base.exists():
            continue
        direct = base / "python.exe"
        if direct.is_file():
            return [str(direct)]
        for child in sorted(base.glob("Python*/python.exe"), reverse=True):
            return [str(child)]

    raise FileNotFoundError(
        "Python n�o encontrado. Instale Python 3.10+ de python.org "
        "e marque 'Add python.exe to PATH'."
    )

print("python_cmd():", python_cmd())