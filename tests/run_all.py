"""
Runner de todos los tests del proyecto.

    python tests/run_all.py

Uno solo en vez de acordarte de tres comandos. Sale con codigo de error != 0
si algo falla, asi que sirve para CI.

Los tests de GUI abren ventanas de verdad (se destruyen solas). Si corres esto
en un server sin display, falla por falta de pantalla, no por el codigo.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

TESTS = [
    ("Parser de streaming", "test_stream_parser.py"),
    ("Contexto de adjuntos", "test_file_context.py"),
    ("Smoke de GUIs", "test_smoke_gui.py"),
]


def main() -> int:
    fallos = []

    for nombre, archivo in TESTS:
        ruta = HERE / archivo
        print(f"\n{'=' * 60}\n{nombre}  ({archivo})\n{'=' * 60}")
        # cwd=ROOT para que los imports de src.* resuelvan.
        proc = subprocess.run(
            [sys.executable, str(ruta)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        # Los scripts de test imprimen su propio reporte; lo mostramos tal cual.
        salida = proc.stdout.strip() or proc.stderr.strip()
        print(salida)
        if proc.returncode != 0:
            fallos.append(nombre)
            if proc.stderr.strip() and proc.stdout.strip():
                print(f"\n--- stderr ---\n{proc.stderr.strip()}")

    print(f"\n{'=' * 60}")
    if fallos:
        print(f"FALLA: {', '.join(fallos)}")
        return 1
    print(f"TODO OK  ({len(TESTS)} suites)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
