"""La configuración que va al repo apunta a España (Granada o remoto)."""

from app.agents import sabueso
from app.fuentes import OfertaEncontrada
from app.llm import PROMPT_TEMPLATE


def _oferta(paises, remoto=False):
    return OfertaEncontrada(fuente="getonbrd", url="https://x/1", titulo="Data Analyst Junior", empresa="E",
                            texto="t", paises=paises, remoto=remoto)


def test_config_filtra_por_espana_o_remoto():
    config = sabueso.cargar_config()
    assert sabueso.pasa_filtro(_oferta(["Spain"]), config["paises"], config["incluir_remoto"])
    assert sabueso.pasa_filtro(_oferta(["España"]), config["paises"], config["incluir_remoto"])
    assert sabueso.pasa_filtro(_oferta(["Remote"], remoto=True), config["paises"], config["incluir_remoto"])
    assert not sabueso.pasa_filtro(_oferta(["Peru"]), config["paises"], config["incluir_remoto"])


def test_config_acepta_titulos_de_ia_y_descarta_senior():
    config = sabueso.cargar_config()
    clave, fuera = config["palabras_clave_titulo"], config["palabras_excluidas_titulo"]
    assert sabueso.titulo_relevante("Junior AI Engineer", clave, fuera)
    assert sabueso.titulo_relevante("Becario/a Inteligencia Artificial", clave, fuera)
    assert not sabueso.titulo_relevante("Senior Data Engineer", clave, fuera)


def test_prompt_de_lupa_traduce_niveles_mcer():
    assert "B1 o B2 -> intermedio" in PROMPT_TEMPLATE
    assert "C1 o C2 -> avanzado" in PROMPT_TEMPLATE


def test_prompt_de_lupa_no_cuenta_lo_que_la_empresa_ofrece_como_requisito():
    # Caso real: "Oportunidades para aprender sobre tecnología, negocios, IA"
    # se extraía como requisito deseable de IA.
    assert "lo que la empresa ofrece enseñar" in PROMPT_TEMPLATE
    assert "la descripción de la empresa" in PROMPT_TEMPLATE
