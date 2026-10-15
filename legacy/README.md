# legacy/ — versiones anteriores de la interfaz

Este directorio NO es producto. Es código archivado.

## Por qué existe

Había 6 archivos de entrada (`gui.py`, `gui_v2.py`, `gui_main.py`,
`gui_cyberpunk.py`, `gui_cymain.py`, `redise-o-*.py`) y no había forma de
saber cuál era el bueno. Eso causó un bug concreto: al borrar un método por
rango de líneas se llevó `choose_model` de otro lado, y `py_compile` no lo
detectó porque **solo valida sintaxis, no atributos**. La app reventaba al
arrancar con un `AttributeError` que culpaba a `tkinter`, no a la clase.

## Qué hay acá

| Archivo | Por qué se archivó |
|---|---|
| `gui.py` | Funcional pero sin streaming y con parcheo frágil de widgets. Reemplazado por `gui_main.py`. |
| `gui_v2.py` | Código muerto: cero llamadas al backend, 3 respuestas simuladas. |

## Los archivos que SÍ importan

Están en la raíz del proyecto:

| Archivo | Estado |
|---|---|
| `gui_main.py` | **GUI principal.** Layout, adjuntos, streaming. |
| `gui_cyberpunk.py` | GUI alternativa: streaming con panel de telemetría. |
| `main.py` | CLI de prueba. |

## Advertencia

**No borres esto sin commitear primero.** Está en el historial de git, así
que siempre se puede recuperar con:

```bash
git log --diff-filter=D --name-only   # ver qué se borró
git checkout <commit> -- gui.py        # recuperarlo
```

Si más adelante querés retomar alguno de estos archivos, decime cuál y
revisamos si conviene rescatarlo o reescribirlo limpio.
