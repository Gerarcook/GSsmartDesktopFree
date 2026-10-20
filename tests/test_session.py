"""
Tests de la sesion (memoria de conversacion).

Lo que mas sale mal aca es SILENCIOSO: si el recorte corta mal, la IA
recibe un historial incoherente y contesta cosas raras sin que nada
falle. Estos tests fijan las reglas del recorte.

Casos que importan:
  - un assistant con content="" hace que el modelo piense que ya contesto
  - cortar en medio de un par deja un user huerfano
  - un mensaje gigante revienta el presupuesto de tokens
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.session import (
    add_user,
    add_assistant,
    build_history,
    estimate_tokens,
    summarize,
    DEFAULT_MAX_TURNS,
)


def par(texto="hola"):
    return [
        {"role": "user", "content": texto},
        {"role": "assistant", "content": "ok"},
    ]


def test_sesion_vacia_da_historial_vacio():
    assert build_history([]) == []


def test_add_user_guarda():
    s = []
    add_user(s, "hola")
    assert s == [{"role": "user", "content": "hola"}]


def test_add_assistant_vacio_no_se_guarda():
    """Un assistant con content vacio hace creer al modelo que respondio."""
    s = []
    add_assistant(s, "")
    add_assistant(s, "   ")
    add_assistant(s, None)
    assert s == [], "una respuesta vacia no debe entrar al historial"


def test_build_history_filtra_roles_invalidos():
    s = [
        {"role": "system", "content": "eres util"},
        {"role": "user", "content": "hola"},
        {"role": "error", "content": "fallo"},
        {"role": "assistant", "content": "ok"},
    ]
    h = build_history(s)
    roles = [m["role"] for m in h]
    assert roles == ["user", "assistant"], f"se colaron roles raros: {roles}"


def test_build_history_ignora_contenido_vacio():
    s = [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "   "},
    ]
    assert build_history(s) == []


def test_ventana_deslizante_respeta_max_turns():
    s = []
    for i in range(30):
        s += par(f"mensaje {i}")
    h = build_history(s, max_turns=3)
    assert len(h) == 6, f"esperaba 6 mensajes (3 turnos), vine {len(h)}"


def test_ventana_empieza_en_un_user():
    """Si recorto a mitad de un par, el primer mensaje no puede ser assistant.

    Un historial que arranca en assistant confunde al modelo.
    """
    s = par("a") + par("b") + par("c") + par("d")
    h = build_history(s, max_turns=1)  # 2 mensajes
    assert h[0]["role"] == "user", f"arranco en {h[0]['role']}, debe ser user"


def test_mensaje_gigante_se_trunca():
    s = [{"role": "user", "content": "X" * 50_000}]
    h = build_history(s, max_chars=1000)
    assert len(h[0]["content"]) < 1200, "el mensaje deberia haberse recortado"
    assert "truncado" in h[0]["content"], "debe avisar que se corto"


def test_turnos_ilimitados():
    s = []
    for i in range(20):
        s += par(f"m{i}")
    h = build_history(s, max_turns=0)  # 0 = sin limite
    assert len(h) == 40


def test_estimate_tokens_aproxima():
    s = [{"role": "user", "content": "a" * 400}]
    assert estimate_tokens(s) == 100


def test_summarize_para_la_ui():
    s = []
    assert "vacia" in summarize(s).lower()
    add_user(s, "hola")
    add_assistant(s, "hola como te va")
    txt = summarize(s)
    assert "1" in txt and "token" in txt.lower()


def test_console_aguanta_emoji():
    """La consola de Windows (cp1252) no puede imprimir emojis.

    MEDIDO oct-2026: hcnsec/Qwen3.8-Flash-Next responde '👋' a un saludo.
    Sin el guard de encoding, main.py moria con:
        UnicodeEncodeError: 'charmap' codec can't encode character '\\U0001f44b'
    """
    import subprocess
    import sys as _sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent
    src_main = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "reconfigure" in src_main, (
        "main.py debe reconfigurar stdout/stderr a utf-8 con errors=replace"
    )
    assert 'errors="replace"' in src_main, (
        "errors=replace es lo que evita el crash; sin eso el emoji mata el proceso"
    )

    # El router tambien imprime, asi que tambien tiene que estar protegido.
    router_src = (ROOT / "src" / "core" / "router.py").read_text(encoding="utf-8")
    assert "reconfigure" in router_src, (
        "router.py imprime diagnosticos y tambien necesita el guard utf-8"
    )

    # Y de verdad: un print de emoji SIN el guard debe fallar (por eso hace
    # falta el guard); CON el guard debe pasar.
    sin_guard = subprocess.run(
        [_sys.executable, "-c", "import sys; print('\\U0001f44b')"],
        capture_output=True, text=True, errors="replace",
    )
    con_guard = subprocess.run(
        [_sys.executable, "-c",
         "import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace'); print('\\U0001f44b')"],
        capture_output=True, text=True, errors="replace",
    )
    assert con_guard.returncode == 0, (
        f"con el guard deberia pasar, fallo: {con_guard.stderr[-200:]}"
    )
    # El sin-guard puede fallar o no segun la consola; si falla, confirma que
    # el guard era necesario. Si pasa, igual esta bien.
    assert sin_guard.returncode == 0 or "charmap" in (sin_guard.stderr or ""), (
        "el caso sin guard deberia fallar por charmap, no por otra cosa"
    )


def test_no_muta_la_sesion_original():
    """build_history no debe modificar la sesion del caller."""
    s = par("a") + par("b") + par("c")
    import copy
    antes = copy.deepcopy(s)
    build_history(s, max_turns=1)
    assert s == antes, "build_history modifico la sesion original"


def test_historico_conserva_el_orden():
    s = [
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": "2"},
        {"role": "user", "content": "3"},
        {"role": "assistant", "content": "4"},
    ]
    h = build_history(s)
    assert [m["content"] for m in h] == ["1", "2", "3", "4"]


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
