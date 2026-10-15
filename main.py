"""
GSsmart Desktop - Punto de entrada (CLI de prueba)

Ejecuta:  python main.py
"""

import asyncio
import sys

from src.core.router import ProviderRouter


async def demo() -> None:
    router = ProviderRouter()

    print("=" * 60)
    print("  GSsmart Desktop - Probador de proveedores")
    print("=" * 60)
    print(f"  Proveedores registrados: {router.providers}")
    print("=" * 60)

    if not router.providers:
        print("No hay proveedores configurados. Revisa src/core/config.py")
        return

    # Probar el primer proveedor registrado (en el .env tuyo es OmniRoute)
    chosen = router.providers[0]

    print(f"\nProveedor elegido: {chosen}")
    print(f"  Base URL: {router.get(chosen).base_url}")
    print(f"  Modelo  : {router.get(chosen).model}")
    print("\nEnviando 'Hola, responde con una sola frase'...\n")

    try:
        response = await router.generate(
            "Hola, responde con una sola frase diciendo que todo funciona.",
            provider=chosen,
        )
        print(f">>> {response}")
        print("\n[OK] Conexion exitosa.")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("\nSugerencias:")
        print("  1. Chequea tu .env (copia .env.example y pone tus keys).")
        print("  2. Si usas un proveedor local, asegurate de que el servidor este corriendo.")
        print("  3. Revisa que el modelo exista en el proveedor.")
        sys.exit(1)
    finally:
        await router.close_all()


if __name__ == "__main__":
    asyncio.run(demo())
