"""
Comprueba el .env antes de arrancar la app, paso a paso:

    python -m scripts.comprobar_env              (solo revisa el formato)
    python -m scripts.comprobar_env --conectar   (además se conecta a la BD)
    python -m scripts.comprobar_env --gemini     (además hace UNA llamada a la IA)

No imprime nunca la API key ni la contraseña: solo dice qué falta o
qué parece mal escrito.
"""

import os
import sys
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

from app.cv.cargador import RAIZ

TABLAS_ESPERADAS = [
    "status", "source", "company", "company_alias", "technology",
    "technology_alias", "job", "job_status_history", "job_technology", "user_skill",
]
FUENTES_ESPERADAS = ["Get on Board", "InfoJobs", "Tecnoempleo"]  # migraciones 002 y 003


def revisar_gemini_key(valor: str | None) -> tuple[list[str], list[str]]:
    """Devuelve (errores, avisos) sobre GEMINI_API_KEY."""
    errores, avisos = [], []
    if not valor:
        return ["GEMINI_API_KEY está vacía. Créala en https://aistudio.google.com/apikey"], avisos
    if valor != valor.strip():
        errores.append("GEMINI_API_KEY tiene espacios al principio o al final.")
    if valor[0] in "\"'" or valor[-1] in "\"'":
        avisos.append("GEMINI_API_KEY está entre comillas: funciona, pero no hacen falta.")
    # No se valida el prefijo: el formato de las claves de Google cambia.
    # Para saber si la clave funciona, usa --gemini.
    return errores, avisos


def revisar_db_url(valor: str | None) -> tuple[list[str], list[str]]:
    """Devuelve (errores, avisos) sobre SUPABASE_DB_URL, sin conectarse."""
    errores, avisos = [], []
    if not valor:
        return ["SUPABASE_DB_URL está vacía. Cópiala de Supabase > Connect > Session pooler."], avisos
    valor = valor.strip().strip("\"'")
    if "[YOUR-PASSWORD]" in valor or "[" in valor:
        errores.append("SUPABASE_DB_URL todavía tiene '[YOUR-PASSWORD]': pon tu contraseña real, sin corchetes.")
    if valor.count("@") > 1:
        errores.append(
            "SUPABASE_DB_URL tiene más de una '@': si tu contraseña lleva '@', escríbela como '%40' "
            "(y '#' como '%23', '/' como '%2F', ':' como '%3A')."
        )
    try:
        partes = urlparse(valor)
        puerto = partes.port
    except ValueError:
        return errores + ["SUPABASE_DB_URL no se puede leer como URL (¿caracteres especiales en la contraseña sin codificar?)."], avisos

    if partes.scheme not in ("postgresql", "postgres"):
        errores.append("SUPABASE_DB_URL debe empezar por 'postgresql://'.")
    if not partes.hostname:
        errores.append("SUPABASE_DB_URL no tiene servidor (host).")
    if not partes.username:
        errores.append("SUPABASE_DB_URL no tiene usuario.")
    if not partes.password:
        errores.append("SUPABASE_DB_URL no tiene contraseña.")
    elif any(c in unquote(partes.password) for c in "@#/:") and partes.password == unquote(partes.password):
        avisos.append("La contraseña tiene caracteres especiales sin codificar; si falla la conexión, codifícalos (ej. '@' -> '%40').")

    host = partes.hostname or ""
    if host.startswith("db.") and host.endswith(".supabase.co"):
        avisos.append(
            "Usas la conexión directa (db.<proyecto>.supabase.co), que solo funciona por IPv6. "
            "Si no conecta desde tu red, usa la cadena 'Session pooler' (host ...pooler.supabase.com)."
        )
    if "pooler.supabase.com" in host and puerto == 6543:
        avisos.append("El puerto 6543 es el 'Transaction pooler'; el README recomienda el 'Session pooler' (puerto 5432).")
    if "pooler.supabase.com" in host and partes.username and "." not in partes.username:
        errores.append("Con el pooler el usuario es 'postgres.<id-del-proyecto>', no solo 'postgres'.")
    return errores, avisos


def conectar_y_revisar_tablas(url: str) -> tuple[list[str], list[str]]:
    import psycopg2

    errores, avisos = [], []
    try:
        conexion = psycopg2.connect(url, connect_timeout=10)
    except Exception as exc:  # se muestra el motivo sin la cadena de conexión
        return [f"No se pudo conectar a la base de datos: {str(exc).strip().splitlines()[0]}"], avisos
    with conexion, conexion.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        existentes = {fila[0] for fila in cur.fetchall()}
        faltan = [t for t in TABLAS_ESPERADAS if t not in existentes]
        if faltan:
            errores.append(
                "Faltan tablas: " + ", ".join(faltan)
                + ". Ejecuta los scripts de sql/ en orden en el SQL Editor de Supabase."
            )
        if "source" in existentes:
            cur.execute("SELECT nombre FROM source")
            fuentes = {fila[0] for fila in cur.fetchall()}
            faltan_fuentes = [f for f in FUENTES_ESPERADAS if f not in fuentes]
            if faltan_fuentes:
                errores.append(
                    "Faltan fuentes en la tabla source: " + ", ".join(faltan_fuentes)
                    + ". Ejecuta sql/002_fuente_getonbrd.sql y sql/003_fuentes_espana.sql."
                )
    conexion.close()
    return errores, avisos


def probar_gemini() -> tuple[list[str], list[str], list[str]]:
    from pydantic import BaseModel

    from app import llm

    class Eco(BaseModel):
        respuesta: str

    r = llm.generar_estructurado('Responde con respuesta="ok".', Eco, agente="lupa")
    if not r.success:
        return [f"La IA no respondió: {r.error[:300]}"], [], []
    return [], [], [f"La IA respondió con el modelo {r.modelo}."]


def _imprimir(titulo: str, errores: list[str], avisos: list[str], info: list[str] = ()) -> None:
    print(f"\n{titulo}: {'OK' if not errores else 'REVISAR'}")
    for e in errores:
        print(f"  [x] {e}")
    for a in avisos:
        print(f"  [!] {a}")
    for i in info:
        print(f"  {i}")


def main(argv: list[str]) -> int:
    ruta_env = RAIZ / ".env"
    if not ruta_env.exists():
        print("No existe .env en la raíz del proyecto. Créalo con:  copy .env.example .env")
        return 1
    load_dotenv(ruta_env, override=True)

    total_errores = 0
    errores, avisos = revisar_gemini_key(os.environ.get("GEMINI_API_KEY"))
    _imprimir("Gemini (GEMINI_API_KEY)", errores, avisos)
    total_errores += len(errores)

    url = os.environ.get("SUPABASE_DB_URL")
    errores, avisos = revisar_db_url(url)
    _imprimir("Base de datos (SUPABASE_DB_URL)", errores, avisos)
    total_errores += len(errores)

    if "--conectar" in argv and not errores:
        errores, avisos = conectar_y_revisar_tablas(url.strip().strip("\"'"))
        _imprimir("Conexión y tablas", errores, avisos)
        total_errores += len(errores)

    if "--gemini" in argv:
        errores, avisos, info = probar_gemini()
        _imprimir("Llamada de prueba a la IA", errores, avisos, info)
        total_errores += len(errores)

    print("\nTodo listo." if total_errores == 0 else f"\n{total_errores} problema(s) por resolver.")
    return 0 if total_errores == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
