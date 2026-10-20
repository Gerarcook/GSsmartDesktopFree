"""
Tests del parser de streaming, contra los payloads REALES de OmniRoute.

Casos capturados en produccion (no inventados):
  1. chunk keepalive   -> choices con delta vacio, model="keepalive"
  2. chunk de usage    -> "choices": []  (rompe data["choices"][0])
  3. chunk de contenido-> delta.content con texto
  4. [DONE]            -> fin del stream
  5. linea no-JSON     -> basura que hay que saltear

Sin esto, un keepalive se cuenta como "primer token" y la latencia que muestra
la UI mide 0ms. Y un choices vacio revienta con IndexError.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.providers.base_provider import (
    parse_stream_line,
    split_reasoning,
    is_reasoning,
)


def test_keepalive_no_es_contenido():
    """El keepalive de OmniRoute NO debeDEVUELVE texto ni contar como token."""
    line = (
        'data: {"id":"chatcmpl-keepalive","object":"chat.completion.chunk",'
        '"created":0,"model":"keepalive","choices":[{"index":0,"delta":{},'
        '"finish_reason":null}]}'
    )
    assert parse_stream_line(line) == "", "keepalive debe ignorarse"


def test_usage_chunk_vacio_no_revienta():
    """OmniRoute manda un chunk de usage con choices: []. Antes daba IndexError."""
    line = (
        'data: {"id":"205aa46aedc34bad","object":"chat.completion.chunk",'
        '"created":1792090424,"model":"MiniCPM-V-4.7-35B-A3B","choices":[],'
        '"usage":{"prompt_tokens":10}}'
    )
    assert parse_stream_line(line) == "", "choices vacio debe ignorarse, no romper"


def test_contenido_real_se_devuelve():
    line = (
        'data: {"id":"abc","object":"chat.completion.chunk","created":1,'
        '"model":"real","choices":[{"index":0,"delta":{"content":"Hola"}}]}'
    )
    assert parse_stream_line(line) == "Hola"


def test_done_termina():
    assert parse_stream_line("data: [DONE]") is None, "DONE debe senalar fin de stream"


def test_basura_se_saltea():
    assert parse_stream_line("data: {no es json") == ""
    assert parse_stream_line("event: ping") == ""
    assert parse_stream_line("") == ""


def test_delta_content_vacio_no_rompe():
    """Primer chunk de un stream real suele traer delta sin content."""
    line = (
        'data: {"id":"abc","object":"chat.completion.chunk","created":1,'
        '"choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}'
    )
    assert parse_stream_line(line) == ""


def test_reasoning_no_se_confunde_con_respuesta_vacia():
    """Los modelos de razonamiento emiten delta.reasoning antes de content.

    Payload REAL de hcnsec/auto -> sensenova-6.8-flash-lite. Sin esto, con
    max_tokens chico el modelo gasta todo el presupuesto pensando, nunca
    llega content, y el router reporta "200 pero sin contenido".
    """
    line = (
        'data: {"id":"x","object":"chat.completion.chunk","created":1,'
        '"model":"sensenova-6.8-flash-lite","choices":[{"index":0,'
        '"delta":{"reasoning":"Thinking Process: 1. Analyze the Request"}}]}'
    )
    razon, texto = split_reasoning(parse_stream_line(line))
    assert texto == "", "el razonamiento NUNCA debe salir como contenido"
    assert razon == "Thinking Process: 1. Analyze the Request", (
        "el razonamiento debe transportarse para que la UI lo muestre"
    )


def test_reasoning_marcado_luego_content_normal():
    """Despues del razonamiento, el contenido vuelve a ser texto normal."""
    razon = (
        'data: {"id":"x","object":"chat.completion.chunk","created":1,'
        '"model":"m","choices":[{"index":0,"delta":{"reasoning":" Thinking"}}]}'
    )
    texto = (
        'data: {"id":"x","object":"chat.completion.chunk","created":1,'
        '"model":"m","choices":[{"index":0,"delta":{"content":"Hola"}}]}'
    )
    r1, t1 = split_reasoning(parse_stream_line(razon))
    r2, t2 = split_reasoning(parse_stream_line(texto))
    assert (r1, t1) == (" Thinking", "")
    assert (r2, t2) == ("", "Hola")


def test_content_manda_sobre_reasoning_si_vienen_juntos():
    line = (
        'data: {"id":"x","object":"chat.completion.chunk","created":1,'
        '"choices":[{"index":0,"delta":{"reasoning":"a","content":"Hola"}}]}'
    )
    razon, texto = split_reasoning(parse_stream_line(line))
    assert texto == "Hola", "el content real debe ganar"
    assert razon == ""


def test_is_reasoning():
    linea_razon = (
        'data: {"id":"x","object":"chat.completion.chunk","created":1,'
        '"choices":[{"index":0,"delta":{"reasoning":"pensando"}}]}'
    )
    linea_texto = (
        'data: {"id":"x","object":"chat.completion.chunk","created":1,'
        '"choices":[{"index":0,"delta":{"content":"Hola"}}]}'
    )
    assert is_reasoning(parse_stream_line(linea_razon)) is True
    assert is_reasoning(parse_stream_line(linea_texto)) is False
    assert is_reasoning("") is False
    assert is_reasoning(None) is False


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
