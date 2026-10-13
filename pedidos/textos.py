"""Normalización de textos para agrupar materiales.

El consolidado de compras agrupa por material del catálogo, no por el texto
libre que escribió cada solicitante. Este módulo produce una "clave" canónica
para que ``CEMENTO``, ``  cemento `` y ``Cemento`` sean el mismo material.

Lo que la normalización **no** hace es deducir equivalencias semánticas:
``50kg`` y ``50 kilogramos`` siguen siendo claves distintas. Eso lo resuelve el
catálogo: el administrador crea "Cemento 50kg" una vez y las cargas siguientes
enlazan a ese material, por lo que el consolidado agrupa exacto.
"""

import re
import unicodedata

_ESPACIOS = re.compile(r'\s+')


def normalizar(texto):
    """Devuelve la clave canónica de ``texto``.

    Minúsculas, sin tildes, sin signos de puntuación y con los espacios
    colapsados a uno solo. Un texto vacío devuelve ``''``.
    """
    if not texto:
        return ''
    descompuesto = unicodedata.normalize('NFKD', str(texto).strip().lower())
    sin_tildes = ''.join(c for c in descompuesto if not unicodedata.combining(c))
    # La puntuación se reemplaza por espacios: "cemento, 50kg" y
    # "cemento 50kg" deben dar la misma clave. El guion se conserva porque
    # "hierro-6mm" y "hierro 6mm" son el mismo material.
    limpio = re.sub(r'[^\w\s-]', ' ', sin_tildes)
    return _ESPACIOS.sub(' ', limpio).strip()