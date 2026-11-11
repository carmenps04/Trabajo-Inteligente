"""
almacen.py -- dónde se guardan los datos privados de la app.

El código sigue trabajando con rutas (data/cv_base.yaml, salidas/...),
pero en vez de leer y escribir el disco directamente se lo pide a este
módulo, que decide el destino:

    archivos  -> el disco, como siempre (por defecto en tu PC y en los tests)
    supabase  -> la tabla `almacen` de tu base de datos
                 (sql/004_almacen.sql), con la ruta relativa como clave

En Cloud Run se usa siempre `supabase`: allí el disco se borra cada vez
que la instancia se reinicia. En tu PC puedes elegirlo con ALMACEN=supabase
en el .env para compartir los datos con la versión publicada (antes sube
los que tengas con `python -m scripts.subir_a_supabase`).
"""

import os
from pathlib import Path

# La misma raíz que app/cv/cargador.py (que importa este módulo).
RAIZ = Path(__file__).resolve().parents[1]

ARCHIVOS = "archivos"
SUPABASE = "supabase"


def modo() -> str:
    elegido = (os.environ.get("ALMACEN") or "").strip().lower()
    if elegido in (ARCHIVOS, SUPABASE):
        return elegido
    if elegido:
        raise ValueError(f"ALMACEN debe ser '{ARCHIVOS}' o '{SUPABASE}', no '{elegido}'.")
    return SUPABASE if os.environ.get("K_SERVICE") else ARCHIVOS


def en_supabase() -> bool:
    return modo() == SUPABASE


def clave(ruta: Path) -> str:
    """Ruta relativa a la raíz del proyecto, con '/': igual en Windows y en Linux."""
    try:
        return Path(ruta).resolve().relative_to(RAIZ.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{ruta} está fuera del proyecto: no se puede guardar en Supabase.") from None


def para_mostrar(ruta: Path) -> str:
    """
    Cómo se anota una ruta en el historial: relativa al proyecto si está
    dentro ("salidas/cv/..."), para que valga igual en tu PC (Windows) y
    en Cloud Run (Linux), que comparten la base de datos.
    """
    try:
        return clave(ruta)
    except ValueError:
        return str(ruta)


def resolver(ruta: str) -> Path:
    """Inversa de para_mostrar: una ruta relativa se interpreta desde la raíz."""
    p = Path(ruta.replace("\\", "/")) if not Path(ruta).is_absolute() else Path(ruta)
    return (p if p.is_absolute() else RAIZ / p).resolve()


def guardar_docx(documento, ruta: Path) -> Path:
    """Guarda un Document de python-docx donde toque (disco o Supabase)."""
    import io

    memoria = io.BytesIO()
    documento.save(memoria)
    escribir_bytes(ruta, memoria.getvalue())
    return ruta


# ---------------------------------------------------------------
# Supabase: una fila por "archivo"
# ---------------------------------------------------------------

def _consultar(sql: str, parametros: tuple, devolver: bool = False):
    from app.repository import get_connection  # import tardío: evita ciclos

    conexion = get_connection()
    try:
        with conexion, conexion.cursor() as cur:
            cur.execute(sql, parametros)
            return cur.fetchone() if devolver else None
    finally:
        conexion.close()


def _leer_db(ruta: Path) -> bytes:
    fila = _consultar("SELECT contenido FROM almacen WHERE clave = %s", (clave(ruta),), devolver=True)
    if fila is None:
        raise FileNotFoundError(str(ruta))
    return bytes(fila[0])


def _escribir_db(ruta: Path, datos: bytes) -> None:
    import psycopg2

    _consultar(
        "INSERT INTO almacen (clave, contenido) VALUES (%s, %s) "
        "ON CONFLICT (clave) DO UPDATE SET contenido = EXCLUDED.contenido, actualizado = now()",
        (clave(ruta), psycopg2.Binary(datos)),
    )


# ---------------------------------------------------------------
# Interfaz pública
# ---------------------------------------------------------------

def existe(ruta: Path) -> bool:
    if en_supabase():
        return _consultar("SELECT 1 FROM almacen WHERE clave = %s", (clave(ruta),), devolver=True) is not None
    return Path(ruta).is_file()


def leer_bytes(ruta: Path) -> bytes:
    """FileNotFoundError si no existe, en los dos modos."""
    return _leer_db(ruta) if en_supabase() else Path(ruta).read_bytes()


def escribir_bytes(ruta: Path, datos: bytes) -> None:
    """Escritura de todo o nada en los dos modos (no queda un archivo a medias)."""
    if en_supabase():
        _escribir_db(ruta, datos)
        return
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_bytes(datos)
    temporal.replace(ruta)


def leer_texto(ruta: Path) -> str:
    return leer_bytes(ruta).decode("utf-8")


def escribir_texto(ruta: Path, texto: str) -> None:
    escribir_bytes(ruta, texto.encode("utf-8"))


def borrar(ruta: Path) -> None:
    if en_supabase():
        _consultar("DELETE FROM almacen WHERE clave = %s", (clave(ruta),))
    else:
        Path(ruta).unlink(missing_ok=True)
