import re
from datetime import date, timedelta


MESES = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

MESES_RE = "|".join(sorted(MESES, key=len, reverse=True))


def _ano(ano, ano_referencia):
    if ano:
        ano = int(ano)
        if ano < 100:
            referencia = ano_referencia or date.today().year
            seculo = referencia // 100
            candidato = seculo * 100 + ano
            if candidato < referencia - 80:
                candidato += 100
            elif candidato > referencia + 20:
                candidato -= 100
            ano = candidato
        return ano
    return ano_referencia or date.today().year


def _adicionar(resultado, dia, mes, ano, texto):
    try:
        data = date(_ano(ano, resultado.get("_ano_referencia")), int(mes), int(dia))
    except (TypeError, ValueError):
        return
    resultado.setdefault("datas", {})[data] = texto.strip()


def _expandir_dias(expressao):
    """Converte '25, 26 e 27' em [25, 26, 27] e '25 a 27' em 25..27."""
    numeros = [int(valor) for valor in re.findall(r"\d{1,2}", expressao)]
    if not numeros:
        return []

    if re.search(r"\ba\b", expressao, re.I) or "-" in expressao:
        if len(numeros) >= 2:
            inicio, fim = numeros[0], numeros[-1]
            if inicio <= fim and fim - inicio <= 31:
                return list(range(inicio, fim + 1))

    return numeros


def _extrair(texto, ano_referencia=None):
    texto = texto or ""
    texto = texto.replace("\u00a0", " ")
    texto = re.sub(r"[\u2013\u2014]", "-", texto)
    texto = re.sub(r"\s+", " ", texto)

    resultado = {"_ano_referencia": ano_referencia, "datas": {}}
    spans_explicitos = []

    # ------------------------------------------------------
    # 1. LISTAS/RANGES POR EXTENSO
    #    25, 26 e 27 de setembro de 2026
    #    25 e 26 de setembro
    #    25 a 27 de setembro de 2026
    # ------------------------------------------------------
    padrao_lista_extenso = re.compile(
        rf"(?P<dias>\d{{1,2}}(?:\s*(?:,|e|a|-)\s*\d{{1,2}})*)"
        rf"\s+de\s+(?P<mes>{MESES_RE})"
        rf"(?:\s+(?:do\s+ano\s+)?de\s+(?P<ano>\d{{2,4}}))?",
        re.I,
    )

    for match in padrao_lista_extenso.finditer(texto):
        mes = MESES[match.group("mes").lower()]
        ano = match.group("ano")
        dias = _expandir_dias(match.group("dias"))
        for dia in dias:
            _adicionar(resultado, dia, mes, ano, match.group(0))
        spans_explicitos.append(match.span())

    # ------------------------------------------------------
    # 2. LISTAS/RANGES NUMÉRICOS
    #    25, 26 e 27/09/2026
    #    25 a 27/09/2026
    #    25, 26 e 27/09
    # ------------------------------------------------------
    padrao_lista_numerica = re.compile(
        r"(?P<dias>\d{1,2}(?:\s*(?:,|e|a|-)\s*\d{1,2})*)"
        r"\s*(?P<sep>[/\-.])\s*(?P<mes>0?[1-9]|1[0-2])"
        r"(?:\s*(?P=sep)\s*(?P<ano>\d{2,4}))?",
        re.I,
    )

    for match in padrao_lista_numerica.finditer(texto):
        mes = int(match.group("mes"))
        ano = match.group("ano")
        dias = _expandir_dias(match.group("dias"))
        for dia in dias:
            _adicionar(resultado, dia, mes, ano, match.group(0))
        spans_explicitos.append(match.span())

    # ------------------------------------------------------
    # 3. DATAS NUMÉRICAS INDIVIDUAIS
    #    25/09/2026, 25/09/26, 25-09-2026, 25.09.2026
    # ------------------------------------------------------
    padrao_numerico = re.compile(
        r"\b(?P<dia>0?[1-9]|[12]\d|3[01])\s*"
        r"(?P<sep>[/\-.])\s*(?P<mes>0?[1-9]|1[0-2])\s*"
        r"(?P=sep)\s*(?P<ano>\d{2,4})\b"
    )

    for match in padrao_numerico.finditer(texto):
        # A lista numérica já registra a mesma data; manter a forma mais específica.
        if any(inicio <= match.start() < fim or inicio < match.end() <= fim for inicio, fim in spans_explicitos):
            continue
        _adicionar(
            resultado,
            match.group("dia"),
            match.group("mes"),
            match.group("ano"),
            match.group(0),
        )
        spans_explicitos.append(match.span())

    # ------------------------------------------------------
    # 4. DIA/MÊS SEM ANO
    #    25/09, 25-09, 25.09
    #    O ano vem de ano_referencia.
    # ------------------------------------------------------
    padrao_dia_mes = re.compile(
        r"\b(?P<dia>0?[1-9]|[12]\d|3[01])\s*"
        r"(?P<sep>[/\-.])\s*(?P<mes>0?[1-9]|1[0-2])\b"
        r"(?!\s*(?P=sep)\s*\d{2,4})"
    )

    for match in padrao_dia_mes.finditer(texto):
        if any(inicio <= match.start() < fim or inicio < match.end() <= fim for inicio, fim in spans_explicitos):
            continue
        _adicionar(
            resultado,
            match.group("dia"),
            match.group("mes"),
            None,
            match.group(0),
        )

    # ------------------------------------------------------
    # 5. "Dia 25" / "dias 25 e 26" COM MÊS JÁ INFORMADO
    #    Não inventamos o mês a partir do nada: usamos o mês
    #    mais próximo que apareceu na mesma frase/trecho.
    # ------------------------------------------------------
    padrao_dias_sem_mes = re.compile(
        r"\b(?:dia|dias|nos dias)\s+"
        r"(?P<dias>\d{1,2}(?:\s*(?:,|e|a|-)\s*\d{1,2})*)"
        rf"\s+(?:de\s+)?(?P<mes>{MESES_RE})\b",
        re.I,
    )
    for match in padrao_dias_sem_mes.finditer(texto):
        mes = MESES[match.group("mes").lower()]
        for dia in _expandir_dias(match.group("dias")):
            _adicionar(resultado, dia, mes, None, match.group(0))

    resultado.pop("_ano_referencia", None)
    return resultado["datas"]


def encontrar_todas_datas(texto, ano_referencia=None):
    """Retorna todas as datas identificáveis no texto do Ofício.

    Cobertura principal:
      - 25/09/26, 25/09/2026, 25-09-26, 25-09-2026, 25.09.2026
      - 25/09, 25-09, 25.09 (ano inferido da referência)
      - 25 de setembro de 2026
      - 25 de setembro
      - 25, 26 e 27 de setembro de 2026
      - 25, 26 e 27 de setembro
      - 25 a 27 de setembro de 2026
      - 25, 26 e 27/09/2026
      - 25 a 27/09/2026
      - listas e formatos misturados no mesmo documento.

    A função não aplica a regra dos 3 dias; ela somente identifica datas.
    """
    datas = _extrair(texto, ano_referencia=ano_referencia)
    return [
        {"texto": texto_original, "data": data}
        for data, texto_original in sorted(datas.items(), key=lambda item: item[0])
    ]
