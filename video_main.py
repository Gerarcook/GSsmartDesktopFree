"""
GSsmart Desktop - Probador de motores de VIDEO (CLI)

    python video_main.py --list
    python video_main.py --test
    python video_main.py --render "texto" --provider "JSON2Video"
    python video_main.py --render "texto" --image keyframe.png --provider "JSON2Video"

Es el equivalente a main.py para el lado video. Sirve para probar los motores
sin levantar la GUI: el render puede tardar minutos y el diagnostico es lo
mismo que va a hacer el boton de la UI.
"""

import argparse
import asyncio
import sys

# Mismo fix que main.py: la consola de Windows (cp1252) no puede imprimir
# caracteres fuera de latin-1 y cualquier emoji en la salida revienta con
# UnicodeEncodeError.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass  # Python < 3.7

from src.core import config


async def cmd_list() -> None:
    print("=" * 64)
    print("  Motores de VIDEO registrados")
    print("=" * 64)
    for name in config.list_video_providers():
        cfg = config.get_video_config(name)
        print(f"  - {name}")
        print(f"      modelo    : {cfg['model']}")
        print(f"      base_url  : {cfg['base_url']}")
        print(f"      tiene key : {'si' if cfg['api_key'] else 'no'}")
    print("=" * 64)


async def cmd_test() -> None:
    print("=" * 64)
    print("  Chequeo de motores de video (request real, no renderiza)")
    print("=" * 64)
    filas = await config.diagnose_video_providers()
    for f in filas:
        marca = "OK  " if f["ok"] else "FALLA"
        print(f"  [{marca}] {f['nombre']}: {f['detalle']}")
        print(f"          modelo={f['modelo']} acepta_imagen={f['acepta_imagen']}")
    print("=" * 64)
    print("  Ojo: esto NO garantiza que el render funcione. Para Wan2.2 el")
    print("  chequeo real es un render: /config puede dar 200 con el backend caido.")


async def cmd_render(a) -> None:
    print(f"  Motor   : {a.provider}")
    if a.model:
        print(f"  Modelo  : {a.model}")
    print(f"  Prompt  : {a.prompt[:100]}")
    print(f"  Imagen  : {a.image or '(ninguna -> text-to-video)'}")
    print(f"  Duracion: {a.duration}s")
    print("-" * 64)
    print("  Renderizando. Con ZeroGPU esto puede tardar 10-15 minutos.")
    print("  Ctrl+C para cortar (el render del servidor sigue vivo).")
    print("-" * 64)

    prov = config.build_video_provider(a.provider)
    if a.model:
        prov.model = a.model
    try:
        res = await prov.render(
            a.prompt,
            image=a.image,
            duration=a.duration,
            seed=a.seed,
        )
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        await prov.close()

    if not res.ok:
        print("\n[ERROR] El motor no devolvio video.")
        sys.exit(1)

    print("\n[OK] Video generado.")
    print(f"  URL      : {res.url}")
    if res.seed is not None:
        print(f"  Seed     : {res.seed}")
    print(f"  Duracion : {res.duration}s")
    if res.credits_remaining is not None:
        print(f"  Quota restante: {res.credits_remaining}")

    if a.out:
        import httpx
        async with httpx.AsyncClient() as c:
            destino = await res.download(c, a.out)
        print(f"  Guardado : {destino}")


def main() -> None:
    p = argparse.ArgumentParser(description="Probador de motores de video")
    p.add_argument("--list", action="store_true", help="Lista los motores registrados")
    p.add_argument("--test", action="store_true", help="Chequea que respondan (no renderiza)")
    p.add_argument("--render", metavar="PROMPT", dest="prompt", help="Genera un video")
    p.add_argument("--provider", default="JSON2Video", help="Nombre del motor")
    p.add_argument("--model", help="Modelo del motor (ej. wan-v2.5 para image-to-video)")
    p.add_argument("--image", help="Keyframe local o URL (para image-to-video)")
    p.add_argument("--duration", type=float, default=5.0)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--out", help="Descarga el mp4 a esta ruta")
    a = p.parse_args()

    if not (a.list or a.test or a.prompt):
        p.print_help()
        return

    if a.list:
        asyncio.run(cmd_list())
    if a.test:
        asyncio.run(cmd_test())
    if a.prompt:
        if a.provider not in config.list_video_providers():
            print(f"Motor desconocido: {a.provider}")
            print(f"Disponibles: {config.list_video_providers()}")
            sys.exit(1)
        asyncio.run(cmd_render(a))


if __name__ == "__main__":
    main()