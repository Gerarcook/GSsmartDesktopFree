"""
Tests del catalogo de modelos.

Lo que mas sale mal aca es mostrar 3241 modelos donde 110 son usables.
Si el filtro deja pasar imagenes/embeddings, la GUI es inutilizable; si
deja pasar todo, tampoco sirve de nada.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.model_catalog import (
    es_modelo_chat,
    clasificar,
    prioridad,
    listar,
    set_model_in_env,
    nombre_base,
    colapsar_variantes,
)


def test_filtra_imagenes():
    for m in [
        "unorouter/cyberrealistic-pony:free",
        "unorouter/juggernaut-xl",
        "stable-diffusion-xl/v1",
        "dall-e-3",
        "midjourney/v6",
        "some/image-model",
    ]:
        assert es_modelo_chat(m) is False, f"deberia filtrar: {m}"


def test_filtra_audio_y_embedding():
    for m in [
        "bge-multilingual-gemma2",
        "text-embedding-3-large",
        "whisper-large-v3",
        "kimi/tts-1",
        "some/rerank-model",
    ]:
        assert es_modelo_chat(m) is False, f"deberia filtrar: {m}"


def test_deja_pasar_modelos_de_texto():
    for m in [
        "hcnsec/Qwen3.8-Flash-Next",
        "unorouter/glm-5.3-flash:free",
        "auto/coding:free",
        "gpt-4o",
        "unorouter/deepseek-r1-distill-qwen-32b:free",
    ]:
        assert es_modelo_chat(m) is True, f"NO deberia filtrar: {m}"


def test_nombre_vacio_no_pasa():
    assert es_modelo_chat("") is False
    assert es_modelo_chat(None) is False


def test_clasificar_detecta_flags():
    c = clasificar("hcnsec/Qwen3.8-Flash-Next")
    assert c["es_alias"] is True
    assert c["es_coding"] is True

    c2 = clasificar("unorouter/glm-5.3-flash:free")
    assert c2["es_free"] is True
    assert c2["es_alias"] is True


def test_detecta_modelos_que_razonan():
    c = clasificar("unorouter/deepseek-r1-distill-qwen-32b:free")
    assert c["razona"] is True


def test_prioridad_pone_alias_primero():
    """Los alias auto/* rutean a modelos que ya respondieron bien."""
    alias = prioridad("auto/coding:free")
    concreto = prioridad("unorouter/gpt-4o:free")
    assert alias < concreto, "un alias deberia probarse antes que uno concreto"


def test_prioridad_prefiere_coding():
    coding = prioridad("hcnsec/Qwen3.8-Flash-Next")
    otro = prioridad("unorouter/allam-2-7b:free")
    assert coding < otro


def test_prioridad_prefiere_no_razonadores():
    """Los que razonan tardan mas; para probar, van despues."""
    rapido = prioridad("hcnsec/Qwen3.8-Flash-Next")
    lento = prioridad("unorouter/deepseek-r1-distill-qwen-32b:free")
    assert rapido < lento


def test_listar_ordena_y_filtra():
    """Lista sucia de entrada debe salir limpia y ordenada."""
    import asyncio

    class FakeProv:
        async def get_available_models(self):
            return [
                "unorouter/cyberrealistic-pony:free",
                "hcnsec/Qwen3.8-Flash-Next",
                "bge-multilingual-gemma2",
                "auto/coding:free",
                None,
                "",
            ]

    out = asyncio.run(listar(FakeProv()))
    assert "unorouter/cyberrealistic-pony:free" not in out
    assert "bge-multilingual-gemma2" not in out
    assert "" not in out and None not in out
    assert out[0] == "auto/coding:free", f"el primero deberia ser el alias: {out}"
    assert out.index("auto/coding:free") < out.index("hcnsec/Qwen3.8-Flash-Next")


def test_listar_deduplica():
    import asyncio

    class FakeProv:
        async def get_available_models(self):
            return ["gpt-4o", "gpt-4o", "gpt-4o"]

    out = asyncio.run(listar(FakeProv()))
    assert out == ["gpt-4o"], f"deberia deduplicar, vino {out}"


def test_listar_tolera_excepcion():
    """Un provider que falla no debe romper la GUI."""
    import asyncio

    class Roto:
        async def get_available_models(self):
            raise RuntimeError("sin conexion")

    assert asyncio.run(listar(Roto())) == []


def test_set_model_escribe_en_env(tmp=None):
    import tempfile
    from pathlib import Path

    d = Path(tempfile.mkdtemp())
    env = d / ".env"
    env.write_text(
        "A=1\nMODEL=viejo\nB=2\n", encoding="utf-8"
    )

    ok, detalle = set_model_in_env("MODEL", "nuevo", env)
    assert ok, f"debio escribir: {detalle}"
    assert "MODEL=nuevo" in env.read_text(encoding="utf-8")
    # No debe tocar el resto.
    txt = env.read_text(encoding="utf-8")
    assert "A=1" in txt and "B=2" in txt


def test_set_model_falla_si_variable_no_existe(tmp=None):
    import tempfile
    from pathlib import Path

    env = Path(tempfile.mkdtemp()) / ".env"
    env.write_text("A=1\n", encoding="utf-8")

    ok, detalle = set_model_in_env("NO_EXISTE", "x", env)
    assert ok is False, "no deberia agregar variables a ciegas"
    assert "no existe" in detalle.lower()


def test_set_model_con_crlf(tmp=None):
    """El fallo que me costo tiempo: regex que no matchea con CRLF."""
    import tempfile
    from pathlib import Path

    env = Path(tempfile.mkdtemp()) / ".env"
    env.write_bytes(b"A=1\r\nMODEL=viejo\r\nB=2\r\n")

    ok, detalle = set_model_in_env("MODEL", "nuevo", env)
    assert ok, f"debio escribir con CRLF: {detalle}"
    assert "MODEL=nuevo" in env.read_text(encoding="utf-8")


def test_set_model_no_deja_bom(tmp=None):
    """Un BOM rompe el parser de dotenv: la linea deja de verse."""
    import tempfile
    from pathlib import Path

    env = Path(tempfile.mkdtemp()) / ".env"
    env.write_text("MODEL=viejo\n", encoding="utf-8")

    set_model_in_env("MODEL", "nuevo", env)
    b = env.read_bytes()
    assert not (b[:3] == b"\xef\xbb\xbf"), "no debe escribir BOM"


def test_set_model_escribe_utf8_valido(tmp=None):
    """Byte invalido en el .env = dotenv deja de leer la linea."""
    import tempfile
    from pathlib import Path

    env = Path(tempfile.mkdtemp()) / ".env"
    env.write_text("# con acentos: año\nMODEL=viejo\n", encoding="utf-8")

    ok, _ = set_model_in_env("MODEL", "nuevo", env)
    assert ok
    env.read_text(encoding="utf-8")  # si tiene bytes malos, revienta


def test_set_model_reemplaza_solo_una_vez(tmp=None):
    import tempfile
    from pathlib import Path

    env = Path(tempfile.mkdtemp()) / ".env"
    env.write_text("MODEL=a\nOTRO=b\nMODEL_2=c\n", encoding="utf-8")

    set_model_in_env("MODEL", "z", env)
    txt = env.read_text(encoding="utf-8")
    assert txt.count("MODEL=") == 1, "no debe duplicar la variable"
    assert "OTRO=b" in txt and "MODEL_2=c" in txt


def test_nombre_base_quita_effort():
    """Las variantes de esfuerzo son el ruido real del catalogo.

    IDs TOMADOS DEL CATALOGO REAL de OmniRoute (oct-2026).
    """
    casos = [
        ("bzl/glm-5.3-flash-xhigh", "bzl/glm-5.3-flash"),
        ("bzl/glm-5.3-low", "bzl/glm-5.3"),
        ("openrouter/openai/gpt-4.1:batch", "openrouter/openai/gpt-4.1"),
        ("unorouter/claude-opus-5.5[1m]-low", "unorouter/claude-opus-5.5"),
    ]
    for variante, esperado in casos:
        assert nombre_base(variante) == esperado, (
            f"{variante} -> {nombre_base(variante)}, esperaba {esperado}"
        )


def test_nombre_base_no_parte_modelos_normales():
    """No debe mutilar un modelo que ya es limpio."""
    for m in [
        "hcnsec/Qwen3.8-Flash-Next",
        "auto/coding",
        "unorouter/glm-5.3-flash:free",
    ]:
        assert nombre_base(m) == m.lower(), f"mutilo {m}: {nombre_base(m)}"


def test_colapsar_variantes_reduce_la_lista():
    """De 2994 variantes a una lista manejable.

    Nota: glm-5.3 y glm-5.3-flash son modelos DISTINTOS y quedan como dos
    grupos. Lo que se colapsa es el sufijo de esfuerzo, no el nombre.
    """
    variantes = [
        "bzl/glm-5.3-flash-xhigh", "bzl/glm-5.3-low", "bzl/glm-5.3-flash",
        "openrouter/openai/gpt-4.1:batch", "openrouter/openai/gpt-4.1",
        "bzl/gpt-6.1-sol", "unorouter/qwen3.8-flash",
    ]
    out = colapsar_variantes(variantes)
    # 7 entradas -> 5 grupos (glm-5.3-flash-xhigh se junta a glm-5.3-flash,
    # gpt-4.1:batch se junta a gpt-4.1).
    assert len(out) == 5, f"esperaba 5 grupos, vine {len(out)}: {out}"
    assert "bzl/glm-5.3-flash-xhigh" not in out
    assert "openrouter/openai/gpt-4.1:batch" not in out


def test_colapsar_prefiere_el_id_mas_corto():
    """Si el modelo base existe, gana sobre la variante."""
    out = colapsar_variantes(["bzl/glm-5.3-flash-xhigh", "bzl/glm-5.3-flash"])
    assert out == ["bzl/glm-5.3-flash"], f"eligio {out}"


def test_colapsar_es_determinista():
    """Dos corridas con distinto orden deben dar lo mismo."""
    a = colapsar_variantes(["bzl/glm-5.3-low", "bzl/glm-5.3-flash-xhigh", "bzl/glm-5.3"])
    b = colapsar_variantes(["bzl/glm-5.3", "bzl/glm-5.3-flash-xhigh", "bzl/glm-5.3-low"])
    assert a == b, f"no es determinista: {a} vs {b}"


def test_listar_aplica_el_colapso():
    import asyncio

    class FakeProv:
        async def get_available_models(self):
            return [
                "bzl/glm-5.3-flash-xhigh",
                "bzl/glm-5.3-flash",
            ]

    out = asyncio.run(listar(FakeProv()))
    assert out == ["bzl/glm-5.3-flash"], f"deberia colapsar a 1, vino {out}"


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
