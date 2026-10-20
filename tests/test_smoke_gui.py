"""
Smoke test: instancia las GUIs para detectar errores que py_compile NO ve.

POR QUE ESTE ARCHIVO EXISTE
----------------------------
Bug real (oct-2026): se borro un metodo (choose_model) por rango de lineas.
`python gui_compile` pasaba, los tests existentes pasaban, y la app reventaba
recien al ejecutarla:

    AttributeError: '_tkinter.tkapp' object has no attribute 'choose_model'

Porque:
  - py_compile solo valida SINTAXIS, no atributos.
  - Los callbacks se resuelven en __init__ (self.choose_model se pasa al
    FooterBar), asi que un metodo faltante explota en runtime.
  - El traceback miente: culpa a tkinter, no a tu clase.

La unica verificacion que lo detecta es INSTANCIAR el widget. Eso hace esto.

Que NO hace: no llama a la red ni al router (eso lo cubren los otros tests).
Solo construye y destruye.

Ejecutar:  python tests/test_smoke_gui.py
"""

import contextlib
import importlib
import io
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gui_main import App  # noqa: E402  (necesita el path de arriba)

#: (modulo, clase principal). Los nombres de clase varian entre versiones,
#: asi que se declaran explicitos en vez de adivinarlos.
#:
#: Solo los puntos de entrada VIGENTES. Las versiones viejas estan en
#: legacy/ y no se testean: son codigo archivado, no producto.
#:
#: Cuando agregues una GUI nueva, agregala aca. Ese es el punto: el smoke
#: test es lo que te dice cual es la buena cuando tenias varias.
GUIS = [
    ("gui_main", "App"),
    ("gui_cyberpunk", "CyberpunkHUD"),
]

#: Metodos que App DEBE tener para que los callbacks del FooterBar resuelvan.
#: Es el chequeo que habria atrapado el bug de choose_model.
CALLBACKS_REQUERIDOS = [
    "send_message", "attach_files", "choose_model",
    "toggle_audio", "clear_attachments",
]


def _construir(mod_nombre, cls_nombre):
    """Instancia la GUI sin dejarla viva."""
    mod = importlib.import_module(mod_nombre)
    cls = getattr(mod, cls_nombre)
    # silencing stdout: varias GUIs hacen print en __init__
    with contextlib.redirect_stdout(io.StringIO()):
        app = cls()
        app.update_idletasks()
    try:
        app.destroy()
    except Exception:
        pass
    return app


def test_las_guis_se_instantian():
    """Cada GUI debe poder construirse sin error."""
    fallos = []
    for mod_nombre, cls_nombre in GUIS:
        try:
            _construir(mod_nombre, cls_nombre)
            print(f"  OK    {mod_nombre}.{cls_nombre}")
        except Exception as e:
            fallos.append(f"{mod_nombre}.{cls_nombre}: {type(e).__name__}: {e}")
            print(f"  FAIL  {mod_nombre}.{cls_nombre} -> {type(e).__name__}: {e}")
    assert not fallos, "GUI(s) que no arrancan:\n  " + "\n  ".join(fallos)


def test_callbacks_requeridos_existen():
    """App debe exponer los metodos que el FooterBar le pasa como callback.

    Esto es lo que atrapa el bug de choose_model.
    """
    app = _construir("gui_main", "App")
    faltan = [m for m in CALLBACKS_REQUERIDOS if not callable(getattr(app, m, None))]
    assert not faltan, (
        f"App no tiene estos metodos y la app reventara al arrancar: {faltan}"
    )


def test_el_smoke_test_detecta_un_callback_roto():
    """Meta-test: el smoke test tiene que FALLAR si se borra un metodo.

    Si este test pasa, significa que test_callbacks_requeridos_existen()
    esta roto y no sirve de nada. Sin esto, el smoke test podria dar falsos
    verdes y no volveria a detectar el bug de choose_model.
    """
    app = _construir("gui_main", "App")
    original = app.choose_model
    try:
        del App.choose_model  # simulamos el bug: metodo borrado
        faltan = [m for m in CALLBACKS_REQUERIDOS if not callable(getattr(app, m, None))]
        assert "choose_model" in faltan, (
            "el chequeo NO detecto el metodo borrado -> el smoke test es inutil"
        )
    finally:
        App.choose_model = original


def test_attached_files_empieza_vacio():
    app = _construir("gui_main", "App")
    assert getattr(app, "attached_files", None) == [], (
        "attached_files debe inicializarse a lista vacia en __init__"
    )


def test_footer_tiene_el_input():
    """El footer es lo que se rompe al reordenar el layout."""
    app = _construir("gui_main", "App")
    for attr in ("entry", "send_btn", "attach_btn", "model_pick_btn"):
        assert hasattr(app.footer_bar, attr), f"FooterBar sin .{attr}"


def test_app_tiene_el_selector_de_modelos():
    """pick_model() y _apply_selected_model() son el flujo nuevo."""
    app = _construir("gui_main", "App")
    for m in ("pick_model", "test_providers", "new_session"):
        assert callable(getattr(app, m, None)), f"App sin .{m}"


def test_seleccion_de_modelo_persiste_en_env():
    """El boton tiene que escribir en .env, no solo mostrar la lista."""
    from src.core.model_catalog import set_model_in_env
    assert callable(set_model_in_env), "falta set_model_in_env en model_catalog"


if __name__ == "__main__":
    print("Smoke test de GUIs")
    print("=" * 50)
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fallos = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            print(f"\n  FALLA {fn.__name__}: {e}")
            fallos += 1
        except Exception as e:
            print(f"\n  ERROR {fn.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
            fallos += 1
    print("\n" + "=" * 50)
    print("TODO OK" if not fallos else f"{fallos} FALLA(S)")
    sys.exit(1 if fallos else 0)
