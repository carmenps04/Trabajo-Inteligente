"""
Sube a Supabase (tabla `almacen`) los datos privados que tienes en tu PC,
para usarlos desde la app publicada en Cloud Run:

    python -m scripts.subir_a_supabase --simular       (solo lista lo que subiría)
    python -m scripts.subir_a_supabase                 (sube; no pisa lo que ya esté allí)
    python -m scripts.subir_a_supabase --sobrescribir  (sube y reemplaza lo que haya)

Sube: tu CV base (y su respaldo), tus respuestas al Preguntón, el
historial de CVs, el plan de Brújula, la actividad de los agentes y
todo lo que hay en salidas/ (los Word generados y sus cambios.json).

No sube: los flujos a medio terminar (data/flujos.sqlite), las ofertas
pendientes del marcador ni los registros de la rutina diaria.

Requisitos: SUPABASE_DB_URL en el .env y haber ejecutado sql/004_almacen.sql.
Tus archivos locales no se borran ni se modifican.
"""

import json
import os
import sys
from pathlib import Path, PureWindowsPath

from dotenv import load_dotenv

from app import almacen
from app.cv.cargador import RAIZ

ARCHIVOS_DATA = [
    "data/cv_base.yaml",
    "data/cv_base.respaldo.yaml",
    "data/respuestas.yaml",
    "data/historial_cv.json",
    "data/brujula_plan.json",
    "data/actividad.jsonl",
]
HISTORIAL = "data/historial_cv.json"


def a_relativa(ruta: str | None) -> str | None:
    """
    'C:\\Users\\x\\Trabajo-Inteligente\\salidas\\cv\\job_4\\CV.docx'
    -> 'salidas/cv/job_4/CV.docx'. Lo que no está en salidas/ queda igual.
    """
    if not ruta:
        return ruta
    partes = PureWindowsPath(ruta).parts if "\\" in ruta else Path(ruta).parts
    if "salidas" not in partes:
        return ruta
    desde = len(partes) - 1 - list(reversed(partes)).index("salidas")
    return "/".join(partes[desde:])


def historial_portable(texto: str) -> str:
    entradas = json.loads(texto)
    for e in entradas:
        e["ruta_cv"] = a_relativa(e.get("ruta_cv"))
        e["ruta_brechas"] = a_relativa(e.get("ruta_brechas"))
        if isinstance(e.get("revision"), dict):
            e["revision"]["ruta"] = a_relativa(e["revision"].get("ruta"))
    return json.dumps(entradas, ensure_ascii=False, indent=1)


def archivos_a_subir(raiz: Path) -> list[str]:
    """Rutas relativas (con '/') que existen en `raiz` y hay que subir."""
    lista = [r for r in ARCHIVOS_DATA if (raiz / r).is_file()]
    salidas = raiz / "salidas"
    if salidas.is_dir():
        lista += sorted(
            p.relative_to(raiz).as_posix() for p in salidas.rglob("*")
            if p.is_file() and not p.name.endswith(".tmp")
        )
    return lista


def subir(raiz: Path, simular: bool = False, sobrescribir: bool = False) -> dict:
    """Lee de `raiz` (tu proyecto) y escribe en Supabase con la misma clave relativa."""
    resumen = {"subidos": [], "ya_estaban": [], "simulados": []}
    for relativa in archivos_a_subir(raiz):
        datos = (raiz / relativa).read_bytes()
        if relativa == HISTORIAL:
            datos = historial_portable(datos.decode("utf-8")).encode("utf-8")
        destino = RAIZ / relativa
        if simular:
            resumen["simulados"].append(relativa)
        elif not sobrescribir and almacen.existe(destino):
            resumen["ya_estaban"].append(relativa)
        else:
            almacen.escribir_bytes(destino, datos)
            resumen["subidos"].append(relativa)
    return resumen


def main(argv: list[str]) -> int:
    load_dotenv(RAIZ / ".env")
    if not os.environ.get("SUPABASE_DB_URL"):
        print("Falta SUPABASE_DB_URL en el .env.")
        return 1
    os.environ["ALMACEN"] = almacen.SUPABASE  # destino: Supabase; el origen se lee del disco
    simular = "--simular" in argv

    if not simular:
        try:
            almacen.existe(RAIZ / "data" / "cv_base.yaml")
        except Exception as exc:
            if "almacen" in str(exc):
                print("No existe la tabla almacen: ejecuta sql/004_almacen.sql en el SQL Editor de Supabase.")
                return 1
            raise

    resumen = subir(RAIZ, simular=simular, sobrescribir="--sobrescribir" in argv)
    if simular:
        print(f"Se subirían {len(resumen['simulados'])} archivo(s):")
        for r in resumen["simulados"]:
            print(f"  {r}")
        return 0
    print(f"Subidos: {len(resumen['subidos'])}")
    for r in resumen["subidos"]:
        print(f"  + {r}")
    if resumen["ya_estaban"]:
        print(f"Ya estaban en Supabase y no se tocaron: {len(resumen['ya_estaban'])} "
              "(usa --sobrescribir para reemplazarlos)")
        for r in resumen["ya_estaban"]:
            print(f"  = {r}")
    if (RAIZ / "data" / "flujos.sqlite").is_file():
        print("Aviso: las adaptaciones de CV a medio terminar no se suben; termínalas en el PC o repítelas.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
