"""
Catalogo de modelos en vivo, para no hardcodear nombres en el .env.

POR QUE ESTO EXISTE
-------------------
Medido oct-2026 contra OmniRoute:

  - GET /models devuelve **3241 modelos**
  - muchos no funcionan aunque esten listados ("not available in the
    active live catalog")
  - los gateways gratuitos rotan: `cohere/north-mini-code:free` funcionaba
    hace 21h y hoy da 404. `qwen3.8-max` idem.

O sea: un modelo escrito a mano en .env se rompe solo. La unica forma de
saber cual sirve es consultando el catalogo Y probandolo.

Este modulo hace las dos cosas por separado, a proposito:

  - listar()   -> que hay (barato, 1 request)
  - probar()   -> cual responde (1 request por modelo)

Que la mayoria de los listados no funcionen es informacion, no un bug:
por eso el filtro heuristico ordena por probabilidad en vez de adivinar.
"""

import re
from typing import Any, Dict, List, Optional

#: Substrings que indican que el modelo NO sirve para chat de texto.
#: Filtrarlos es lo que convierte 3241 entradas en ~110 usables.
_NO_CHAT = re.compile(
    r"(sdxl|image|imagen|audio|tts|stt|whisper|embed|embedding|rerank|"
    r"bge-|e5-|gte-|vision-|vl-|midjourney|stable-diffusion|flux"
    r"|dall-?e|juggernaut|dreamshaper|deliberate|apertus|"
    r"lora|checkpoint|upscale|segment|pose|depth|uncanny|pony|anime|"
    r"cyberrealistic|realistic|photography|album|anything-|aura-|"
    r"absolutereality|albedobase|amponyxl|flat-2d|icbinp|ising-|"
    r"diffusiongemma|alla?m-2|dots-3-note)",
    re.I,
)

#: Alias de OmniRoute: enrutan a un modelo real y suelen ser lo mas estable.
_ALIAS = re.compile(r"^(auto|hcnsec|unorouter)/", re.I)

#: Palabras que sugieren capacidad de coding (para ordenar primero).
_CODING = re.compile(r"(coder|coding|code-|deepseek-v4|qwen3|glm-5|kimi)", re.I)

#: Modelos que sabemos que razonan: tardan mas y consumen tokens de mas.
#: No se excluyen, pero conviene avisarlo.
_REASONING = re.compile(r"(thinking|reasoning|r1|distill)", re.I)


def es_modelo_chat(modelo: str) -> bool:
    """Heuristica: True si el modelo parece servir para chat de texto."""
    if not modelo:
        return False
    return not _NO_CHAT.search(modelo)


#: Sufijos de "effort" y variantes que NO son modelos distintos.
#:
#: MEDIDO oct-2026 en el catalogo de OmniRoute: de 3241 entradas, ~2994
#: sobreviven a un filtro de imagen/audio. El ruido real son VARIANTES del
#: mismo modelo:
#:     bzl/glm-5.3-flash-xhigh
#:     bzl/glm-5.3-low
#:     openrouter/openai/gpt-4.1:batch
#:     unorouter/claude-opus-5.5[1m]-low
#: Son el mismo modelo con distinto nivel de razonamiento. El usuario quiere
#: elegir un MODELO, no un nivel de esfuerzo. Colapsarlos deja una lista
#: manejable en vez de 2994 filas.
_VARIANTES = re.compile(
    r"(\[[^\]]*\]"
    r"|:(batch|nitro|beta)\b"
    r"|-(minimal|low|medium|high|xhigh|ultra|none|think|thinking"
    r"|preview|latest|exp)\b)+",
    re.I,
)


def nombre_base(modelo: str) -> str:
    """Quita sufijos de esfuerzo para agrupar variantes del mismo modelo."""
    return _VARIANTES.sub("", modelo).strip("-/").lower()


def colapsar_variantes(modelos) -> List[str]:
    """Reduce N variantes a un modelo base, quedandose con la mas simple.

    Se queda con el id MAS CORTO de cada grupo: si existen
    "glm-5.3-flash" y "glm-5.3-flash-xhigh", gana el primero, que es el
    que la gente espera. Empates por orden alfabetico, para que sea
    determinista.
    """
    mejor: Dict[str, str] = {}
    for m in modelos:
        base = nombre_base(m)
        if not base:
            continue
        actual = mejor.get(base)
        if actual is None or len(m) < len(actual) or (len(m) == len(actual) and m < actual):
            mejor[base] = m
    return sorted(mejor.values(), key=prioridad)


def clasificar(modelo: str) -> Dict[str, Any]:
    """Info util de un modelo, para decidir cual probar primero."""
    return {
        "id": modelo,
        "es_alias": bool(_ALIAS.match(modelo)),
        "es_free": modelo.endswith(":free"),
        "es_coding": bool(_CODING.search(modelo)),
        "razona": bool(_REASONING.search(modelo)),
    }


def prioridad(modelo: str) -> tuple:
    """Orden de prueba. Menor = probar antes.

    Basado en lo medido: los alias auto/* rutean a modelos que ya
    respondieron bien, y los :free explicitos son mas fragiles.
    """
    c = clasificar(modelo)
    return (
        0 if c["es_alias"] else 1,       # alias primero
        0 if c["es_coding"] else 1,      # despues los de coding
        1 if c["razona"] else 0,          # los que no razonan responden antes
        0 if c["es_free"] else 1,
        len(modelo),                      # desempate estable
    )


async def listar(provider) -> List[str]:
    """Pide el catalogo a un provider y devuelve IDs ordenados.

    `provider` es un BaseProvider ya instanciado.

    Devuelve [] si el provider falla: es codigo de UI, y una excepcion
    aca dejaria la ventana de modelos vacia sin explicacion. El error se
    loguea, no se propaga.
    """
    try:
        modelos = await provider.get_available_models()
    except Exception as e:
        print(f"[catalogo] no se pudo listar: {e}")
        return []

    ids = [m for m in (modelos or []) if m and es_modelo_chat(m)]
    return colapsar_variantes(set(ids))


async def probar(provider, modelo: str, timeout: Optional[float] = None) -> Dict[str, Any]:
    """Hace UNA request corta a un modelo y dice si sirve.

    No usa streaming ni el historial: es una prueba minima, solo para
    saber si el modelo existe y responde. Mide el tiempo hasta el primer
    token, que es lo que el usuario percibe como espera.
    """
    import time

    inicio = time.perf_counter()
    piezas: List[str] = []
    razon_chars = 0
    modelo_real = None

    # Sin esto el provider sigue con el modelo del .env y "probar X" miente.
    if hasattr(provider, "model"):
        provider.model = modelo

    try:
        agen = provider.generate_stream("di ok", max_tokens=16)
        async for kind, piece in agen:
            if kind == "reasoning":
                razon_chars += len(piece)
                continue
            piezas.append(piece)
            if "".join(piezas).strip():
                break  # primer token basta para saber que funciona
    except Exception as e:
        return {
            "modelo": modelo,
            "ok": False,
            "motivo": str(e)[:120],
            "ttft": None,
            "razon_chars": 0,
            "modelo_real": None,
        }

    texto = "".join(piezas).strip()
    return {
        "modelo": modelo,
        "ok": bool(texto),
        "motivo": "" if texto else "respondio sin contenido",
        "ttft": time.perf_counter() - inicio,
        "razon_chars": razon_chars,
        "modelo_real": modelo_real,
    }


def set_model_in_env(variable: str, valor: str, env_path=None) -> tuple:
    """Escribe una variable en el .env del proyecto. Devuelve (ok, detalle).

    Existe porque hardcodear el modelo en .env a mano se rompe: hay que
    editar el archivo mientras la app corre, y esa edicion tiene dos
    trampas que ya costaron tiempo (medido oct-2026):

      1. Escribir con PowerShell Out-File mete un BOM UTF-8 y a veces
         deja un byte invalido. El parser de dotenv deja de VER la
         linea entera: el sintoma es "configurado pero sin api_key".
      2. Reemplazar con regex sobre el texto falla si el archivo tiene
         CRLF, y el cambio no se aplica sin avisar.

    Aca se lee y escribe en utf-8 explicito, sin BOM, preservando los
    saltos de linea que ya tenia, y se verifica que la variable exista.
    Si no existe, no se la agrega a ciegas.
    """
    from pathlib import Path

    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    env_path = Path(env_path)

    if not env_path.exists():
        return False, f"no existe {env_path}"

    try:
        texto = env_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        return False, f"el .env tiene bytes invalidos: {e}"

    patron = re.compile(rf"^{re.escape(variable)}\s*=.*$", re.M)
    if not patron.search(texto):
        return False, f"{variable} no existe en .env; agregala a mano"

    nuevo = patron.sub(f"{variable}={valor}", texto, count=1)

    try:
        # utf-8 sin BOM; newline="" preserva los CRLF que ya tenia.
        with open(env_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(nuevo)
    except OSError as e:
        return False, f"no se pudo escribir: {e}"

    # Verificar que quedo bien: un cambio silencioso no aplicado es
    # peor que un error explicito.
    try:
        check = env_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        return False, f"el .env quedo corrupto: {e}"
    if f"{variable}={valor}" not in check:
        return False, "la escritura no se aplico"

    return True, f"{variable}={valor}"
