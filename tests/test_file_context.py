"""
Tests de build_file_context().

Los casos que importan son los que fallan SILENCIOSAMENTE en produccion:
un .pnginjectado como texto, un archivo de 4GB que reventaba el prompt,
o un adjunto ilegible que hacia fallar el mensaje entero.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.file_context import (
    build_file_context,
    looks_binary,
    read_text_file,
    describe_files,
)

TMP = Path(__file__).resolve().parent / "_tmp_fixtures"


def _fresh_dir():
    """Cada test necesita el directorio: teardown lo borra al final."""
    TMP.mkdir(exist_ok=True)
    return TMP


def setup_module():
    TMP.mkdir(exist_ok=True)


def teardown_module():
    if TMP.exists():
        for f in TMP.iterdir():
            f.unlink()
        TMP.rmdir()


def test_lee_archivo_de_texto():
    _fresh_dir()
    p = TMP / "notas.txt"
    p.write_text("hola mundo", encoding="utf-8")
    ctx = build_file_context([str(p)])
    assert "hola mundo" in ctx
    assert "notas.txt" in ctx
    assert "FIN: notas.txt" in ctx


def test_detecta_binario_por_extension():
    _fresh_dir()
    p = TMP / "imagen.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    assert looks_binary(p) is True


def test_detecta_binario_por_byte_nulo():
    """El caso peligroso: un PNG sin extension, o renombrado a .txt."""
    _fresh_dir()
    p = TMP / "tramposo.txt"
    p.write_bytes(b"esto parece texto\x00pero es binario")
    assert looks_binary(p) is True


def test_binario_no_entra_al_prompt():
    _fresh_dir()
    p = TMP / "foto.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 40)
    ctx = build_file_context([str(p)])
    # No debe meter el contenido, solo reportar que lo omite.
    assert "no se puede leer como texto" in ctx
    assert "foto.png" in ctx


def test_trunca_archivo_enorme():
    _fresh_dir()
    p = TMP / "enorme.txt"
    p.write_text("A" * 100_000, encoding="utf-8")
    ctx = build_file_context([str(p)], max_file_bytes=1_000)
    assert "contenido truncado" in ctx
    # El bloque truncado no debe pesar mas que el limite (mas el encabezado).
    assert len(ctx) < 3_000


def test_archivo_inexistente_no_revienta():
    ctx = build_file_context([str(TMP / "no_existe.txt")])
    assert "no existe" in ctx


def test_ningun_archivo_ilegible_no_falla_el_mensaje():
    """Un adjunto malo no debe impedir mandar el mensaje."""
    _fresh_dir()
    p = TMP / "bueno.txt"
    p.write_text("esto si", encoding="utf-8")
    malo = TMP / "malo.bin"
    malo.write_bytes(b"\x00\x01\x02")
    ctx = build_file_context([str(malo), str(p), str(TMP / "fantasma.txt")])
    assert "esto si" in ctx
    assert "malo.bin" in ctx
    assert "fantasma.txt" in ctx


def test_lista_vacia_devuelve_vacio():
    assert build_file_context([]) == ""


def test_cp1252_no_revienta():
    """Archivo en cp1252 (default de Windows), no utf-8."""
    _fresh_dir()
    p = TMP / "acentos.txt"
    p.write_bytes("año acción ñ".encode("cp1252"))
    ctx = build_file_context([str(p)])
    assert "FIN: acentos.txt" in ctx


def test_utf8_con_acentos():
    _fresh_dir()
    p = TMP / "utf8.txt"
    p.write_text("acción del año", encoding="utf-8")
    ctx = build_file_context([str(p)])
    assert "acción del año" in ctx


def test_limita_cantidad_de_archivos():
    _fresh_dir()
    paths = []
    for i in range(20):
        p = TMP / f"f{i}.txt"
        p.write_text(f"contenido {i}", encoding="utf-8")
        paths.append(str(p))
    ctx = build_file_context(paths, max_files=5)
    assert "limite de 5" in ctx
    assert "f0.txt" in ctx
    assert "f19.txt" not in ctx


def test_describe_para_la_ui():
    assert describe_files([]) == "Sin archivos adjuntos"
    assert "notas.txt" in describe_files([str(TMP / "notas.txt")])


def test_el_contexto_marca_limite_para_que_el_modelo_lo_sepa():
    """Si truncamos, el modelo debe poder notarlo y no inventar el resto."""
    _fresh_dir()
    p = TMP / "largo.txt"
    p.write_text("Z" * 50_000, encoding="utf-8")
    ctx = build_file_context([str(p)], max_file_bytes=500)
    assert "truncado" in ctx


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  OK    {nombre}")
            except AssertionError as e:
                print(f"  FALLA {nombre}: {e}")
                fallos += 1
            except Exception as e:
                print(f"  ERROR {nombre}: {type(e).__name__}: {e}")
                fallos += 1
    print(f"\n{'TODO OK' if not fallos else str(fallos) + ' FALLAS'}")
    sys.exit(1 if fallos else 0)
