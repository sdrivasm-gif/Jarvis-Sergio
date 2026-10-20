"""Crea el acceso directo «Jarvis» en el escritorio: abre la interfaz (python -m jarvis --ui) con la consola minimizada.
Uso: .venv\\Scripts\\python scripts\\crear_acceso_directo.py [--carpeta RUTA]"""
import argparse
import base64
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
NOMBRE = "Jarvis.lnk"
MAX_DETALLE = 300  # caracteres del error de PowerShell que se muestran
# Script constante: las rutas llegan por variables de entorno, así que no hay comillas que escapar ni nada que inyectar.
SCRIPT_LNK = (
    "$ErrorActionPreference = 'Stop'\n"
    "$carpeta = if ($env:JARVIS_LNK_CARPETA) { $env:JARVIS_LNK_CARPETA } else { [Environment]::GetFolderPath('Desktop') }\n"
    "$ruta = Join-Path $carpeta $env:JARVIS_LNK_NOMBRE\n"
    "$a = (New-Object -ComObject WScript.Shell).CreateShortcut($ruta)\n"
    "$a.TargetPath = $env:JARVIS_LNK_PYTHON\n"
    "$a.Arguments = '-m jarvis --ui'\n"
    "$a.WorkingDirectory = $env:JARVIS_LNK_RAIZ\n"
    "$a.WindowStyle = 7\n"
    "$a.Description = 'Jarvis: interfaz local'\n"
    "$a.Save()\n"
    "Write-Output $ruta\n"
)


def comando() -> list[str]:
    codificado = base64.b64encode(SCRIPT_LNK.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", codificado]


def variables(python: Path, raiz: Path, carpeta: Path | None) -> dict[str, str]:
    return {"JARVIS_LNK_PYTHON": str(python), "JARVIS_LNK_RAIZ": str(raiz),
            "JARVIS_LNK_CARPETA": str(carpeta) if carpeta else "", "JARVIS_LNK_NOMBRE": NOMBRE}


def crear(carpeta: Path | None = None, python: Path | None = None, ejecutar=None) -> Path:
    python = python or Path(sys.executable)
    if python.name.lower() == "pythonw.exe":  # Jarvis necesita consola para Ctrl+C y para cerrarse
        python = python.with_name("python.exe")
    if not python.is_file():
        raise SystemExit(f"No encuentro {python}.")
    try:
        r = (ejecutar or subprocess.run)(
            comando(), env={**os.environ, **variables(python, RAIZ, carpeta)}, check=True, capture_output=True,
            text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"No pude crear el acceso directo: {detalle_error(e)}") from None
    return Path(r.stdout.strip())


def detalle_error(e: subprocess.CalledProcessError) -> str:
    # El stderr de PowerShell puede traer bytes no válidos o caracteres de control: se limpia antes de mostrarlo.
    # ponytail: si PowerShell lo da en CLIXML se ve tal cual; extraer el mensaje si molesta.
    texto = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    texto = " ".join("".join(c if c.isprintable() else " " for c in texto).split())
    if not texto:
        return f"PowerShell terminó con el código {e.returncode}."
    return texto if len(texto) <= MAX_DETALLE else texto[:MAX_DETALLE] + "…"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Crea el acceso directo de Jarvis en el escritorio.")
    p.add_argument("--carpeta", type=Path, help="carpeta donde crearlo (por defecto, el escritorio)")
    ruta = crear(carpeta=p.parse_args(argv).carpeta)
    print(f"Acceso directo creado: {ruta}")
    print("Ábrelo con doble clic. Para cerrar Jarvis, cierra su consola (minimizada en la barra de tareas).")
    return 0


# ponytail: sin icono propio; con rutas de caracteres raros la salida de PowerShell puede verse mal en consola.
if __name__ == "__main__":
    sys.exit(main())
