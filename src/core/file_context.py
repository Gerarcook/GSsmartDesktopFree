"""
Convierte archivos adjuntos en contexto para el prompt.

Por que existe: al router se le pueden pasar rutas, pero un endpoint
OpenAI-compatible NO sabe leer el disco del cliente. Si mandamos
`{"files": ["C:/x.py"]}` en el body, la API lo ignora o lo rechaza.
El modelo solo ve `messages`. Entonces hay que LEER el archivo aca y
 Meter su contenido en el prompt.

Este modulo hace esa lectura con limites explicitos, porque los archivos
del usuario son de tamano y formato desconocidos:

  - tope por archivo y total   -> un .iso de 4GB no puede entrar al prompt
  - deteccion de binarios      -> un PNG como texto es ruido puro
  - utf-8 con fallback         -> la mayoria de los .py estan en utf-8, no en cp1252
  - truncado explicito         -> si se corta, el modelo lo sabe y no inventa el resto
"""

from pathlib import Path
from typing import Iterable, List, Optional, Sequence

#: Tope por archivo. ~200KB de texto son del orden de 50k tokens: plenty.
MAX_FILE_BYTES = 200_000

#: Tope total del contexto de adjuntos.
MAX_TOTAL_BYTES = 600_000

#: Cantidad maxima de archivos por mensaje. Evita prompts giganticos.
MAX_FILES = 12

#: Se leen los primeros N bytes para sniffear binarios antes de cargar todo.
_SNIFF_BYTES = 8192

#: Extensiones que sabemos que son binarias. Los sniffea igual, esto es la
#: primera pasada para no ni intentar leer un .png de 40MB.
_BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tiff",
    ".pdf", ".zip", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tar",
    ".exe", ".dll", ".so", ".dylib", ".class", ".jar",
    ".mp3", ".mp4", ".wav", ".ogg", ".avi", ".mov", ".mkv",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".db", ".sqlite", ".bin", ".pyc", ".woff", ".woff2", ".ttf", ".eot",
})


class FileReadError(Exception):
    """No se pudo leer un archivo. El resto de la lista sigue adelante."""


def looks_binary(path: Path) -> bool:
    """True si el archivo parece binario.

    Dos señales: extension conocida, o un byte nulo en los primeros bytes.
    El byte nulo es lo que mas falla: un PNG decodificado a latin-1 es
    'texto' valido para Python y llenaria el prompt de basura.
    """
    if path.suffix.lower() in _BINARY_SUFFIXES:
        return True
    try:
        with path.open("rb") as fh:
            return b"\x00" in fh.read(_SNIFF_BYTES)
    except OSError:
        # Si no se puede ni sniffear, asumimos texto y dejamos que la
        # lectura real falle con un mensaje util.
        return False


def read_text_file(path: Path, max_bytes: int = MAX_FILE_BYTES) -> str:
    """Lee un archivo de texto, truncando en max_bytes.

    utf-8 primero porque es el default real. Si falla, probamos cp1252, que
    es el default en Windows y cubre acentos y eñes sin romper.
    """
    raw = path.read_bytes()

    if len(raw) > max_bytes:
        raw = raw[:max_bytes]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # cp1252 nunca falla (cubre todos los bytes 0-255), asi que es un
        # fallback seguro. errors="replace" por si acaso.
        text = raw.decode("cp1252", errors="replace")

    return text


def format_file_block(path: Path, content: str, truncated: bool) -> str:
    """Envuelve un archivo con marcadores que el modelo puede citar."""
    nombre = path.name
    aviso = "\n... [contenido truncado]" if truncated else ""
    return f"--- ARCHIVO: {nombre} ---\n{content}{aviso}\n--- FIN: {nombre} ---"


def build_file_context(
    paths: Sequence[str],
    max_files: int = MAX_FILES,
    max_file_bytes: int = MAX_FILE_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
) -> str:
    """Convierte rutas en un bloque de texto para el prompt.

    Nunca lanza excepcion por un archivo fallido: lo saltea y lo reporta
    como nota. Un adjunto ilegible no deberia impedir mandar el mensaje.

    Devuelve string vacio si no hay nada legible.
    """
    if not paths:
        return ""

    bloques: List[str] = []
    omitidos: List[str] = []
    usado = 0

    for ruta in paths[:max_files]:
        path = Path(ruta)
        if not path.is_file():
            omitidos.append(f"{path.name} (no existe)")
            continue

        if looks_binary(path):
            omitidos.append(f"{path.name} (binario, no se puede leer como texto)")
            continue

        try:
            contenido = read_text_file(path, max_file_bytes)
        except OSError as e:
            omitidos.append(f"{path.name} (error de lectura: {e.strerror})")
            continue

        truncado = path.stat().st_size > max_file_bytes
        if usado + len(contenido) > max_total_bytes:
            restantes = max_total_bytes - usado
            if restantes <= 0:
                omitidos.append(f"{path.name} (excede el limite total)")
                continue
            contenido = contenido[:restantes]
            truncado = True

        usado += len(contenido)
        bloques.append(format_file_block(path, contenido, truncado))

    if len(paths) > max_files:
        omitidos.append(
            f"{len(paths) - max_files} archivo(s) mas (limite de {max_files})"
        )

    if not bloques:
        if omitidos:
            return "ARCHIVOS ADJUNTOS (ninguno legible):\n" + "\n".join(
                f"- {o}" for o in omitidos
            )
        return ""

    encabezado = f"ARCHIVOS ADJUNTOS ({len(bloques)}):\n"
    if omitidos:
        encabezado += "Omitidos: " + "; ".join(omitidos) + "\n"

    return encabezado + "\n" + "\n\n".join(bloques) + "\n"


def describe_files(paths: Iterable[str]) -> str:
    """Resumen corto de los adjuntos, para mostrar en la UI."""
    paths = list(paths)
    if not paths:
        return "Sin archivos adjuntos"
    nombres = [Path(p).name for p in paths]
    if len(nombres) == 1:
        return f"1 archivo: {nombres[0]}"
    return f"{len(nombres)} archivos: " + ", ".join(nombres[:3]) + (
        f" y {len(nombres) - 3} mas" if len(nombres) > 3 else ""
    )
