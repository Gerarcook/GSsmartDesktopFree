"""
Configuracion central: aca se registran TODOS los proveedores
disponibles y se leen las claves desde el archivo .env

Para agregar un proveedor nuevo:
  1. Importa su clase
  2. Agregalo al diccionario PROVIDERS con un nombre unico

El programa va a poder usarlo al instante, sin tocar nada mas.
"""

import os
from typing import Dict, Optional, Type
from pathlib import Path

from dotenv import load_dotenv

from src.providers.base_provider import BaseProvider
from src.providers.openrouter_provider import OpenRouterProvider
from src.providers.custom_provider import CustomProvider

from src.media import JSON2VideoProvider, WanProvider, BytePlusProvider, DEFAULT_SPACE

# Forzamos que busque el .env en la RAIZ del proyecto (donde vive main.py),
# para que importe las variables aunque la app se corra desde otra carpeta.
_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env", override=False)

# NOTA: no logueamos nada aqui a proposito. Este modulo se importa en cada
# arranque y cualquier print queda en consola, logs y capturas de pantalla.
# Para diagnosticar credenciales usar debug_key.py / debug_config.py, que
# enmascaran los valores.


# ------------------------------------------------------------------
# Registro de proveedores
# La clave es el nombre que se muestra en la app.
# El dict interno dice que clase usar y de donde sacar api_key,
# base_url y model.
# ------------------------------------------------------------------
PROVIDERS: Dict[str, dict] = {
    "OmniRoute": {
        "class": OpenRouterProvider,
        "api_key": os.getenv("OMNIROUTE_API_KEY", ""),
        "base_url": os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1"),
        "model": os.getenv("OMNIROUTE_MODEL", "auto/coding:free"),
        "model_env": "OMNIROUTE_MODEL",
        "api_key_env": "OMNIROUTE_API_KEY",
        "base_url_env": "OMNIROUTE_BASE_URL",
    },
    # OpenAI directo. OJO: sin OPENAI_API_KEY real esto da 401 garantizado,
    # porque el default del base_url es api.openai.com. Si no la tenes,
    # dejalo sin base_url y el router lo omite.
    "OpenAI": {
        "class": CustomProvider,
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL", ""),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "model_env": "OPENAI_MODEL",
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
    },
    "OpenRouter": {
        "class": OpenRouterProvider,
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "model": os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free"),
        "model_env": "OPENROUTER_MODEL",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
    },
    "Custom (compatible OpenAI)": {
        "class": CustomProvider,
        "api_key": os.getenv("CUSTOM_API_KEY", ""),
        "base_url": os.getenv("CUSTOM_BASE_URL", ""),
        "model": os.getenv("CUSTOM_MODEL", "local-model"),
        "model_env": "CUSTOM_MODEL",
        "api_key_env": "CUSTOM_API_KEY",
        "base_url_env": "CUSTOM_BASE_URL",
    },
    # Kimi / Moonshot. API key PROPIA (platform.kimi.com), sin proxy: es la
    # unica forma limpia de usar esto. OJO: la cuenta necesita saldo; con 0
    # saldo la API responde 429 "account is suspended due to insufficient
    # balance" aunque la key sea valida (verificado oct-2026).
    "Kimi": {
        "class": CustomProvider,
        "api_key": os.getenv("KIMI_API_KEY", ""),
        "base_url": os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1"),
        "model": os.getenv("KIMI_MODEL", "kimi-k2.7-code"),
        "model_env": "KIMI_MODEL",
        "api_key_env": "KIMI_API_KEY",
        "base_url_env": "KIMI_BASE_URL",
    },
    # Modelos locales (LM Studio / Ollama / vLLM). Sin key ni saldo.
    # Es la unica via que no depende de que alguien te de acceso.
    "Local (LM Studio)": {
        "class": CustomProvider,
        "api_key": os.getenv("LOCAL_API_KEY", ""),
        "base_url": os.getenv("LOCAL_BASE_URL", "http://localhost:1234/v1"),
        "model": os.getenv("LOCAL_MODEL", "qwen2.5-coder-1.5b-instruct"),
        "model_env": "LOCAL_MODEL",
        "api_key_env": "LOCAL_API_KEY",
        "base_url_env": "LOCAL_BASE_URL",
    },
}


# ------------------------------------------------------------------
# Motores de VIDEO
#
# Van aparte de PROVIDERS a proposito. PROVIDERS es de chat: el router
# hace router.generate("di ok") contra cada uno y espera texto. Un motor de
# video necesita una imagen y devuelve un mp4, asi que si estuviera en
# PROVIDERS el boton "Testear conexiones" lo marcaria roto siempre.
# Ver src/media/base_video_provider.py.
#
# OJO: estos NO entran en diagnose_providers() ni en el fallback del router.
# Para video usá diagnose_video_providers() de mas abajo.
# ------------------------------------------------------------------
VIDEO_PROVIDERS: Dict[str, dict] = {
    "JSON2Video": {
        "class": JSON2VideoProvider,
        "api_key": os.getenv("JSON2VIDEO_API_KEY", ""),
        "base_url": os.getenv("JSON2VIDEO_BASE_URL", "https://api.json2video.com/v2"),
        "model": os.getenv("JSON2VIDEO_MODEL", "seedance-v1.5-pro"),
    },
    "Wan2.2 (HF)": {
        "class": WanProvider,
        "api_key": "",  # el Space de HF no pide key
        "base_url": os.getenv("WAN_SPACE", DEFAULT_SPACE),
        "model": "wan2.2-14b-fast",
    },
    # BytePlus ModelArk / Seedance. Factura por TOKENS, no por creditos:
    # 500.000 gratis por modelo. El AK/SK de IAM NO sirve aca, la API de Ark
    # usa Bearer.
    "BytePlus Seedance": {
        "class": BytePlusProvider,
        "api_key": os.getenv("ARK_API_KEY", ""),
        "base_url": os.getenv("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3"),
        "model": os.getenv("ARK_MODEL", "seedance-1-0-pro-250528"),
    },
}






def api_key_env_for(name: str) -> str:
    return (PROVIDERS.get(name) or {}).get("api_key_env") or ""


def base_url_env_for(name: str) -> str:
    return (PROVIDERS.get(name) or {}).get("base_url_env") or ""


def apply_provider_runtime(name: str, *, api_key=None, base_url=None, model=None) -> None:
    """Actualiza PROVIDERS + os.environ en caliente (sin reiniciar)."""
    if name not in PROVIDERS:
        return
    cfg = PROVIDERS[name]
    if api_key is not None:
        cfg["api_key"] = api_key
        env = cfg.get("api_key_env")
        if env:
            os.environ[env] = api_key
    if base_url is not None:
        cfg["base_url"] = base_url
        env = cfg.get("base_url_env")
        if env:
            os.environ[env] = base_url
    if model is not None:
        cfg["model"] = model
        env = cfg.get("model_env")
        if env:
            os.environ[env] = model


def mask_secret(value: str, keep: int = 4) -> str:
    """Muestra solo los ultimos keep chars. No loguea el valor completo."""
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= keep:
        return "*" * len(v)
    return ("*" * max(8, len(v) - keep)) + v[-keep:]


def model_env_for(name: str) -> str:
    """Variable de .env que guarda el modelo de este proveedor."""
    cfg = PROVIDERS.get(name) or {}
    return cfg.get("model_env") or ""


def resolve_active_provider(preferred: Optional[str] = None) -> Optional[str]:
    """Elige el proveedor a usar: preferred si esta configurado, si no el primero listo."""
    listos = configured_providers()
    if not listos:
        return None
    if preferred and preferred in listos:
        return preferred
    return listos[0]


def get_provider_class(name: str) -> Type[BaseProvider]:
    """Devuelve la clase del proveedor por nombre."""
    if name not in PROVIDERS:
        raise KeyError(f"Proveedor '{name}' no registrado. Disponibles: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]["class"]


def get_provider_config(name: str) -> dict:
    """Devuelve la config completa (clase + credenciales) de un proveedor."""
    if name not in PROVIDERS:
        raise KeyError(f"Proveedor '{name}' no registrado. Disponibles: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]


def list_providers() -> list:
    """Devuelve los nombres de todos los proveedores registrados."""
    return list(PROVIDERS.keys())


def is_configured(name: str) -> bool:
    """True si el proveedor tiene lo minimo para intentar una request.

    Criterio: base_url no vacia. La API key NO es obligatoria porque los
    proveedores locales (LM Studio, Ollama) no la necesitan, y exigirla
    dejaria fuera justamente la unica via que no depende de saldo.

    Ojo: esto dice "esta configurado", NO "va a funcionar". Un proveedor con
    base_url y key pero sin saldo igual esta configurado y falla con 429.
    Para eso hace falta probarlo de verdad (ver diagnose_providers).
    """
    cfg = PROVIDERS.get(name)
    if not cfg:
        return False
    return bool((cfg.get("base_url") or "").strip())


def configured_providers() -> list:
    """Solo los proveedores que tienen base_url configurada."""
    return [n for n in PROVIDERS if is_configured(n)]


def provider_report() -> list:
    """Resumen de cada proveedor para diagnostics y para la UI.

    No hace red: solo mira la config. Para saber si responde de verdad
    hay que usar diagnose_providers().
    """
    filas = []
    for name, cfg in PROVIDERS.items():
        base = (cfg.get("base_url") or "").strip()
        key = (cfg.get("api_key") or "").strip()
        estado = "listo"
        if not base:
            estado = "sin base_url"
        elif not key and "localhost" not in base and "127.0.0.1" not in base:
            estado = "sin api_key"
        filas.append({
            "nombre": name,
            "estado": estado,
            "base_url": base or "-",
            "modelo": cfg.get("model") or "-",
            "tiene_key": bool(key),
        })
    return filas


async def diagnose_providers() -> list:
    """Prueba cada proveedor configurado y dice si realmente responde.

    Distingue lo que la config NO puede saber: una key valida con la cuenta
    sin saldo se ve bien en la config y falla con 429 en la red.

    Cuesta una request por proveedor. Pensado para un boton "Testear
    conexiones" en la GUI, no para llamar en cada arranque.
    """
    from src.core.router import ProviderRouter

    router = ProviderRouter()
    resultados = []
    try:
        for name in router.providers:
            try:
                texto = await router.generate("di ok", provider=name, fallback=False)
                resultados.append({
                    "nombre": name,
                    "ok": bool(texto),
                    "detalle": (texto or "")[:60] or "respuesta vacia",
                })
            except Exception as e:
                resultados.append({
                    "nombre": name,
                    "ok": False,
                    "detalle": str(e)[:120],
                })
    finally:
        await router.close_all()
    return resultados


# ------------------------------------------------------------------
# Helpers de VIDEO (espejo de los de chat, pero sobre VIDEO_PROVIDERS)
# ------------------------------------------------------------------

def list_video_providers() -> list:
    """Nombres de los motores de video registrados."""
    return list(VIDEO_PROVIDERS.keys())


def get_video_config(name: str) -> dict:
    if name not in VIDEO_PROVIDERS:
        raise KeyError(f"Motor de video '{name}' no registrado. Disponibles: {list_video_providers()}")
    return VIDEO_PROVIDERS[name]


def build_video_provider(name: str):
    """Instancia un motor de video por nombre.

    A diferencia de los de chat, el motor queda con el cliente httpx abierto:
    hay que cerrarlo con close() o await close_all_video().
    """
    cfg = get_video_config(name)
    cls = cfg["class"]
    if cls is WanProvider:
        # WanProvider construye su host a partir del space, no de una base_url.
        return cls(space=cfg["base_url"], model=cfg["model"])
    return cls(api_key=cfg["api_key"], base_url=cfg["base_url"], model=cfg["model"])


async def diagnose_video_providers() -> list:
    """Prueba real cada motor de video. Devuelve lista de dicts.

    A diferencia de diagnose_providers(), no renderiza nada: llama
    is_available(), que es barato. OJO con la interpretacion: para el Space de
    HF, /config 200 NO garantiza que el render funcione (cuando el backend
    estaba caido, /config daba 200 y generate_video devolvia event:error).
    Para video el chequeo definitivo es un render de verdad.
    """
    filas = []
    for name in VIDEO_PROVIDERS:
        prov = None
        try:
            prov = build_video_provider(name)
            ok, detalle = await prov.is_available()
            filas.append({
                "nombre": name,
                "ok": ok,
                "detalle": detalle,
                "acepta_imagen": prov.supports_image(),
                "modelo": prov.model,
            })
        except Exception as e:
            filas.append({
                "nombre": name,
                "ok": False,
                "detalle": str(e)[:120],
                "acepta_imagen": False,
                "modelo": VIDEO_PROVIDERS[name].get("model", "-"),
            })
        finally:
            if prov is not None:
                await prov.close()
    return filas
