"""
Rutina diaria: Centinela arma el resumen y te avisa. La corre la
tarea programada de Windows (scripts/programar_tarea.ps1), pero
también se puede correr a mano:

    python -m scripts.rutina_diaria
    python -m scripts.rutina_diaria --con-sabueso   (busca también en Get on Board)
    python -m scripts.rutina_diaria --sin-sabueso   (nunca busca, aunque esté activo)
    python -m scripts.rutina_diaria --brujula       (fuerza el informe semanal)

La búsqueda automática de Sabueso está DESACTIVADA por defecto: las
ofertas se pegan a mano. Para reactivarla, pon `en_rutina_diaria: true`
en config/sabueso.yaml.

Los lunes (o con --brujula) Brújula actualiza el plan de estudio y
deja un informe en salidas/brujula/.

Deja un registro en data/logs/rutina.log.
"""

import logging
import sys
from dataclasses import asdict
from datetime import date

from app import services
from app.agents import centinela, sabueso
from app.cv.cargador import RAIZ

RUTA_LOG = RAIZ / "data" / "logs" / "rutina.log"


def _configurar_log() -> logging.Logger:
    RUTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(RUTA_LOG, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("rutina")


def debe_buscar(argv: list[str], config: dict) -> bool:
    """¿Corre Sabueso en esta rutina? Los argumentos mandan sobre la config."""
    if "--sin-sabueso" in argv:
        return False
    if "--con-sabueso" in argv:
        return True
    return bool(config.get("en_rutina_diaria", False))


def main() -> int:
    log = _configurar_log()
    resultado_sabueso = None

    try:
        config_sabueso = sabueso.cargar_config()
    except Exception:
        log.exception("No se pudo leer config/sabueso.yaml; Sabueso no correrá")
        config_sabueso = {}

    if not debe_buscar(sys.argv, config_sabueso):
        log.info("Sabueso: no se ejecuta (en_rutina_diaria: false en config/sabueso.yaml o --sin-sabueso).")
    else:
        log.info("Sabueso: buscando ofertas nuevas...")
        try:
            resultado_sabueso = asdict(sabueso.ejecutar(config_sabueso))
            log.info(
                "Sabueso: %d encontradas, %d registradas, %d sin registrar, %d ya estaban, "
                "%d fuera de filtro, %d errores",
                resultado_sabueso["encontradas"], len(resultado_sabueso["registradas"]),
                len(resultado_sabueso["descartadas"]),
                resultado_sabueso["ya_registradas"], resultado_sabueso["fuera_de_filtro"],
                len(resultado_sabueso["errores"]),
            )
            for motivo in resultado_sabueso["descartadas"] + resultado_sabueso["errores"]:
                log.warning("Sabueso: %s", motivo[:300])
        except Exception:
            # Si Sabueso falla, Centinela igual avisa de los seguimientos.
            log.exception("Sabueso falló")

    try:
        resumen = centinela.armar_resumen()
    except Exception:
        log.exception("Centinela no pudo leer la base de datos")
        centinela.notificar("la rutina diaria falló", f"Revisa {RUTA_LOG}")
        return 1

    ruta = centinela.guardar_resumen(centinela.resumen_markdown(resumen, resultado_sabueso), resumen["fecha"])
    log.info("Centinela: resumen guardado en %s", ruta)
    from app.agents import eventos
    eventos.registrar(
        "centinela",
        f"Resumen del día: {len(resumen['nuevas'])} ofertas nuevas y "
        f"{len(resumen['recordatorios'])} postulaciones para hacer seguimiento.",
        "ok", "rutina",
    )

    titulo, cuerpo = centinela.texto_notificacion(resumen)

    if date.today().weekday() == 0 or "--brujula" in sys.argv:
        try:
            plan = services.generar_plan_estudio()
            if plan["error"]:
                log.warning("Brújula: no se pudo actualizar el plan: %s", plan["error"][:300])
            ruta_informe = services.generar_informe_brujula()
            log.info("Brújula: informe semanal en %s", ruta_informe)
            cuerpo += " Brújula actualizó tu plan de estudio."
        except Exception:
            log.exception("Brújula falló")

    if not centinela.notificar(titulo, cuerpo):
        log.warning("No se pudo mostrar la notificación de Windows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
