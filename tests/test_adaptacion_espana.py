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


def test_prompt_de_lupa_trata_alternativas_conceptos_y_nombres():
    # Caso real: "Power BI, Tableau and/or Domo" daba tres obligatorias,
    # "business intelligence" salía como tecnología y "XLS" no era Excel.
    assert "márcalas TODAS como\n  requirement_type=preferred" in PROMPT_TEMPLATE
    assert '"business intelligence"' in PROMPT_TEMPLATE
    assert '-> "Excel"' in PROMPT_TEMPLATE


def test_pluma_no_nombra_el_puesto_en_el_perfil():
    # Caso real: el perfil acababa en "orientando mi perfil hacia la
    # posición de Sales Analyst".
    from app.agents.pluma import PROMPT_REDACCION
    assert "no nombres el puesto ni la empresa" in PROMPT_REDACCION


def test_textos_de_los_documentos_en_espanol_de_espana():
    from app.cv.cargador import RAIZ
    texto = (RAIZ / "app" / "agents" / "imprenta.py").read_text(encoding="utf-8")
    assert "lo usaste" not in texto
    assert "Agrégalo" not in texto
