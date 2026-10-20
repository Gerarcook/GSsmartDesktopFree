"""
Tokens visuales de GSsmart Desktop.

Fuente UNICA de color y tipografia. La idea es que ningun widget hardcodee
un "#00d9ff": si el dia de mañana se quiere cambiar el acento, se cambia
aca y no hay que grep por 40 archivos.

POR QUE ESTA SEPARADO Y NO DENTRO DE LA GUI
    Hay dos interfaces (gui_main.py y gui_cyberpunk.py) con paletas distintas.
    Antes cada una tenia su propio dict y se desincronizaban: gui_cyberpunk
    se habia puesto neón y gui_main seguia en el azul plano de CustomTkinter,
    que es justamente la diferencia que se queria borrar. Los tokens viven en
    src/ para que las dos puedan leerlos.

Nota sobre la fuente
    Se usa Consolas para los elementos de HUD (etiquetas, codigo, valores
    numericos) y Segoe UI para texto corrido (chat, input, ayuda). Todo en
    Consolas se ve muy "hacker" pero cansa la vista en parrafos largos de
    respuesta del modelo.
"""

from typing import Dict


#: Paleta cyberpunk. Fondo casi negro con acento neón.
COLORS: Dict[str, str] = {
    "bg": "#05070D",            # fondo de la ventana
    "panel": "#0A111C",         # paneles y barra inferior
    "panel_raised": "#0E1726",  # campos, barras de progreso
    "cyan": "#00F0FF",          # acento principal, botones primarios
    "cyan_mid": "#00A8B5",      # hover del acento
    "cyan_dim": "#0B3A44",      # bordes y acentos apagados
    "magenta": "#FF2A6D",       # acento de error / acciones destructivas
    "magenta_dim": "#3D0F22",
    "green": "#05FFA1",         # estado conectado
    "text": "#E4F6F8",
    "text_muted": "#7A8EA0",
    "text_dim": "#3A4A5C",
    "grid": "#0C1624",
}

#: Tipografia. HUD en monoespaciada, texto corrido en proporcional.
FONT_MONO = "Consolas"
FONT_UI = "Segoe UI"


#: Alturas y radios. Centralizados para que los paneles y los botones
#: compartan la misma "textura" y no se vean pegados.
RADIUS_PANEL = 12
RADIUS_FIELD = 8
RADIUS_PILL = 50


def mix(hex_a: str, hex_b: str, t: float) -> str:
    """Interpola dos colores hex. t=0 devuelve a, t=1 devuelve b.

    Sirve para estados disabled/hover calculados en vez de inventar un tercer
    color a mano que despues no combina con nadie.
    """
    a = hex_a.lstrip("#")
    b = hex_b.lstrip("#")
    out = []
    for i in (0, 2, 4):
        ca, cb = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out.append(round(ca + (cb - ca) * t))
    return "#" + "".join(f"{v:02X}" for v in out)


#: Estados derivados de la paleta, para no hardcodear el gris de "apagado".
DIM = {
    "accent_disabled": mix(COLORS["cyan"], COLORS["bg"], 0.55),
    "surface_disabled": mix(COLORS["panel"], COLORS["bg"], 0.5),
}