from scripts.comprobar_env import revisar_db_url, revisar_gemini_key

POOLER = "postgresql://postgres.abcdefghij:MiClave123@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"


def test_gemini_vacia_es_error():
    errores, _ = revisar_gemini_key("")
    assert errores


def test_gemini_valida_sin_avisos():
    assert revisar_gemini_key("AIzaSyFALSAfalsaFALSAfalsa") == ([], [])


def test_gemini_con_otro_formato_no_avisa():
    # Las claves de AI Studio no siempre empiezan por "AIza".
    assert revisar_gemini_key("OtroFormatoDeClave123") == ([], [])


def test_gemini_con_espacios_es_error():
    errores, _ = revisar_gemini_key(" AIzaSyFALSA ")
    assert errores


def test_url_del_pooler_valida():
    assert revisar_db_url(POOLER) == ([], [])


def test_url_con_placeholder_de_supabase():
    errores, _ = revisar_db_url(POOLER.replace("MiClave123", "[YOUR-PASSWORD]"))
    assert any("YOUR-PASSWORD" in e for e in errores)


def test_url_con_arroba_sin_codificar():
    errores, _ = revisar_db_url(POOLER.replace("MiClave123", "Mi@Clave"))
    assert any("%40" in e for e in errores)


def test_url_con_arroba_codificada_es_valida():
    assert revisar_db_url(POOLER.replace("MiClave123", "Mi%40Clave"))[0] == []


def test_pooler_sin_id_de_proyecto_en_el_usuario():
    errores, _ = revisar_db_url(POOLER.replace("postgres.abcdefghij", "postgres"))
    assert any("postgres.<id-del-proyecto>" in e for e in errores)


def test_conexion_directa_avisa_de_ipv6():
    _, avisos = revisar_db_url("postgresql://postgres:clave@db.abcdefghij.supabase.co:5432/postgres")
    assert any("IPv6" in a for a in avisos)


def test_esquema_incorrecto():
    errores, _ = revisar_db_url("mysql://u:p@host:3306/db")
    assert errores
