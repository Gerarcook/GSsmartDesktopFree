"""
Tests del registro de proveedores.

Foco: evitar que un proveedor "listo" en la config地去 a la red sin estar
realmente configurado. Y que las funciones nuevas no rompan el contrato
viejo (list_providers / get_provider_config).

Caso real que motiva estos tests: la key de Kimi daba GET /models 200
(key valida) pero chat/completions 429 por saldo insuficiente. La config
NO puede verlo: por eso existe diagnose_providers(), y aca probamos que
la parte estatica al menos no mienta sobre lo que SÍ sabe.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core import config


def test_registro_no_vacio():
    assert len(config.PROVIDERS) > 0


def test_todos_los_proveedores_tienen_clase():
    for nombre, cfg in config.PROVIDERS.items():
        assert "class" in cfg, f"{nombre} sin clase"
        assert hasattr(cfg["class"], "generate_stream"), (
            f"{nombre}: la clase no cumple el contrato de BaseProvider"
        )


def test_is_configured_detecta_base_url_vacia():
    assert config.is_configured("Custom (compatible OpenAI)") is False, (
        "sin base_url no puede considerarse configurado"
    )


def test_is_configured_ignora_nombre_inexistente():
    assert config.is_configured("no-existe") is False


def test_proveedor_local_no_exige_api_key():
    """Los proveedores locales no tienen key y eso es valido.

    Exigirla dejaria fuera la unica via que no depende de saldo.
    """
    cfg = config.PROVIDERS.get("Local (LM Studio)")
    if cfg is None:
        return  # si lo borran, el test no aplica
    base = cfg.get("base_url") or ""
    assert config.is_configured("Local (LM Studio)") is True, (
        "un proveedor local con base_url debe estar configurado aunque la key este vacia"
    )
    assert "localhost" in base or "127.0.0.1" in base


def test_configured_providers_es_subconjunto():
    todos = set(config.list_providers())
    conf = set(config.configured_providers())
    assert conf.issubset(todos), "configured_providers() devolvio algo no registrado"


def test_provider_report_tiene_las_claves_esperadas():
    filas = config.provider_report()
    assert len(filas) == len(config.PROVIDERS)
    for f in filas:
        for clave in ("nombre", "estado", "base_url", "modelo", "tiene_key"):
            assert clave in f, f"falta '{clave}' en el reporte"


def test_provider_report_marca_sin_api_key():
    filas = {f["nombre"]: f for f in config.provider_report()}
    openrouter = filas.get("OpenRouter")
    if openrouter is None:
        return
    assert openrouter["tiene_key"] is False, (
        "en este repo OpenRouter no tiene key; si la agregaste, actualiza el test"
    )
    assert openrouter["estado"] == "sin api_key"


def test_get_provider_config_falla_claro():
    try:
        config.get_provider_config("no-existe")
        raise AssertionError("deberia lanzar KeyError")
    except KeyError as e:
        assert "no-existe" in str(e), "el error debe decir cual proveedor falta"


def test_diagnose_providers_es_coroutine():
    """Debe ser awaitable (hace red, no puede ser sync)."""
    import inspect
    assert inspect.iscoroutinefunction(config.diagnose_providers)


def test_sin_api_key_no_manda_header_authorization():
    """El bug del "Bearer " vacio.

    Con api_key vacia, ambos providers mandaban 'Authorization: Bearer '
    y httpx tiraba "Illegal header value b'Bearer '" ANTES de salir a la
    red: un error que no dice nada del problema real. Medido oct-2026.
    """
    import asyncio
    from src.providers.custom_provider import CustomProvider
    from src.providers.openrouter_provider import OpenRouterProvider

    async def check():
        for clase in (CustomProvider, OpenRouterProvider):
            p = clase(api_key="", base_url="http://localhost:1/v1", model="m")
            try:
                h = await (p._auth_headers() if hasattr(p, "_auth_headers") else p._headers())
                assert "Authorization" not in h, (
                    f"{clase.__name__} manda Authorization sin key: "
                    f"{h.get('Authorization')!r}"
                )
            finally:
                await p.close()

    asyncio.run(check())


def test_ningun_metodo_arma_bearer_sin_key():
    """Ningun metodo puede construir 'Bearer ' a mano.

    El bug original estaba en TRES lugares de OpenRouterProvider
    (_post, generate_stream y get_available_models), y testear solo el
    helper no los cubria. Ahora los tres usan _auth_headers(); este test
    falla si alguien vuelve a armar el dict inline.
    """
    import inspect
    from src.providers import openrouter_provider as orp

    fuente = inspect.getsource(orp)
    apariciones = [ln.strip() for ln in fuente.splitlines()
                   if "Bearer {self.api_key}" in ln]
    assert len(apariciones) == 1, (
        f"'Bearer {{self.api_key}}' aparece {len(apariciones)} veces; debe "
        f"aparecer UNA sola vez (dentro de _auth_headers). Apariciones: {apariciones}"
    )


def test_con_api_key_manda_bearer_correcto():
    import asyncio
    from src.providers.custom_provider import CustomProvider
    from src.providers.openrouter_provider import OpenRouterProvider

    async def check():
        for clase in (CustomProvider, OpenRouterProvider):
            p = clase(api_key="sk-test-123", base_url="http://localhost:1/v1", model="m")
            try:
                h = await (p._auth_headers() if hasattr(p, "_auth_headers") else p._headers())
                assert h["Authorization"] == "Bearer sk-test-123"
                assert h["Authorization"] == "Bearer sk-test-123".rstrip()
            finally:
                await p.close()

    asyncio.run(check())


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
