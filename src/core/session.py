"""
Session: memoria de la conversacion en formato OpenAI.

POR QUE ESTA EN src/ Y NO EN LA GUI
-------------------------------------
Porque es logica de negocio, no de presentacion. Si vive en el widget,
despues hay dos GUIs (gui_main y gui_cyberpunk) y cada una reimplementa
la ventana deslizante, el formato y el limite de tokens. Ademas un
cliente de linea de comandos no tendria como reutilizarlo.

QUE RESUELVE
------------
Hoy cada mensaje se manda sin contexto: la IA no recuerda nada de lo que
se hablo antes. Esto arma la lista de mensajes que ya acepta
`provider.generate_stream(history=...)`.

Decisiones:
  - Ventana deslizante por N mensajes: el contexto crece sin limite y
    termina comiendo tokens (y plata) o chocando el limite del modelo.
  - Solo entran mensajes user/assistant con texto. Los avisos del sistema,
    los errores y los adjuntos NO van al historial: no son conversacion.
  - Contar de a pares. Cortar en medio de un par (user sin assistant)
    confunde al modelo mas que no mandar nada de ese turno.
"""

from typing import Any, Dict, List, Optional

#: Pares user/assistant que se mantienen. 20 mensajes ~10 turnos, que
#: entra en la ventana de casi todos los modelos sin gastarse.
DEFAULT_MAX_TURNS = 10

#: Se recorta por caracteres, no solo por turnos, porque un solo mensaje
#: puede ser enorme (pegar un archivo de 600KB).
MAX_CHARS_PER_MESSAGE = 8000


def add_user(session: List[Dict[str, str]], text: str) -> None:
    session.append({"role": "user", "content": text})


def add_assistant(session: List[Dict[str, str]], text: str) -> None:
    if not (text or "").strip():
        # Nunca guardar una respuesta vacia: un assistant con content=""
        # hace que el modelo piense que ya contesto.
        return
    session.append({"role": "assistant", "content": text})


def build_history(
    session: List[Dict[str, str]],
    max_turns: int = DEFAULT_MAX_TURNS,
    max_chars: int = MAX_CHARS_PER_MESSAGE,
) -> List[Dict[str, str]]:
    """Arma el historial a enviar, ya recortado.

    Devuelve lista vacia si no hay nada usable. Nunca lanza.
    """
    if not session:
        return []

    # 1. Solo roles validos y con contenido.
    limpio: List[Dict[str, str]] = []
    for m in session:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            limpio.append({"role": role, "content": content})
    if not limpio:
        return []

    # 2. Recortar mensajes gigantes de entrada.
    for m in limpio:
        if len(m["content"]) > max_chars:
            m["content"] = m["content"][:max_chars] + "\n... [mensaje truncado]"

    # 3. Ventana deslizante por turnos completos.
    if max_turns > 0:
        limite = max_turns * 2
        if len(limpio) > limite:
            limpio = limpio[-limite:]
            # Si arranco en medio de un par, saco el user huerfano hasta
            # que empiece en un "user".
            while limpio and limpio[0]["role"] != "user":
                limpio.pop(0)

    return limpio


def estimate_tokens(session: List[Dict[str, str]]) -> int:
    """Estimacion grosera: ~4 caracteres por token.

    Sirve para decidir si hay que recortar antes de gastar una request.
    No es exacto y no pretende serlo.
    """
    total = sum(len(m.get("content") or "") for m in session)
    return total // 4


def summarize(session: List[Dict[str, str]]) -> str:
    """Resumen corto para la UI."""
    if not session:
        return "Sesion vacia"
    usuarios = sum(1 for m in session if m.get("role") == "user")
    return f"{usuarios} mensajes ~{estimate_tokens(session)} tokens"
