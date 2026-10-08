import re
from datetime import date


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

_UNIDADES = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2,
    "três": 3, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11,
    "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14,
    "quinze": 15, "dezesseis": 16, "dezasseis": 16,
    "dezessete": 17, "dezassete": 17, "dezoito": 18, "dezenove": 19,
}

_DEZENAS = {
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
    "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90,
}

_CENTENAS = {
    "cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200,
    "trezentos": 300, "trezentas": 300, "quatrocentos": 400,
    "quatrocentas": 400, "quinhentos": 500, "quinhentas": 500,
    "seiscentos": 600, "seiscentas": 600, "setecentos": 700,
    "setecentas": 700, "oitocentos": 800, "oitocentas": 800,
    "novecentos": 900, "novecentas": 900,
}


def _numero_por_extenso(expressao):
    """Converte números simples por extenso em inteiros."""
    texto = re.sub(r"\s+", " ", (expressao or "").lower().strip())
    tokens = [token for token in re.split(r"\s+|-", texto) if token != "e"]
    if not tokens:
        return None

    total = 0
    atual = 0
    teve_numero = False

    for token in tokens:
        if token in _UNIDADES:
            atual += _UNIDADES[token]
            teve_numero = True
        elif token in _DEZENAS:
            atual += _DEZENAS[token]
            teve_numero = True
        elif token in _CENTENAS:
            atual += _CENTENAS[token]
            teve_numero = True
        elif token == "mil":
            total += (atual or 1) * 1000
            atual = 0
            teve_numero = True
        else:
            return None

    valor = total + atual
    return valor if teve_numero else None


def _ano(ano, ano_referencia=None):
    """Ano expresso prevalece; sem ano, usa sempre o ano corrente."""
    if ano is None or str(ano).strip() == "":
        return date.today().year

    valor = int(str(ano).strip())
    if valor < 100:
        valor += (date.today().year // 100) * 100
    return valor


def _adicionar(resultado, dia, mes, ano, texto):
    try:
        data = date(_ano(ano, resultado.get("_ano_referencia")), int(mes), int(dia))
    except (TypeError, ValueError):
        return
    resultado.setdefault("datas", {})[data] = texto.strip()


def _expandir_dias(expressao):
    """Converte listas/ranges de dias em números."""
    numeros = [int(valor) for valor in re.findall(r"\d{1,2}", expressao)]
    if not numeros:
        return []

    if re.search(r"\ba\b", expressao, re.I) or "-" in expressao:
        if len(numeros) >= 2:
            inicio, fim = numeros[0], numeros[-1]
            if inicio <= fim and fim - inicio <= 31:
                return list(range(inicio, fim + 1))

    return numeros


def _normalizar_espacos(texto):
    texto = (texto or "").replace("\u00a0", " ")
    texto = re.sub(r"[\u2013\u2014]", "-", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _extrair(texto, ano_referencia=None):
    texto = _normalizar_espacos(texto)
    resultado = {"_ano_referencia": ano_referencia, "datas": {}}
    spans_explicitos = []

    # 1. Listas/ranges por extenso com ano numérico.
    padrao_lista_extenso = re.compile(
        rf"(?P<dias>\d{{1,2}}(?:\s*(?:,|e|a|-)\s*\d{{1,2}})*)"
        rf"\s+de\s+(?P<mes>{MESES_RE})"
        rf"(?:\s+(?:do\s+ano\s+)?de\s+(?P<ano>\d{{2,4}}))?",
        re.I,
    )
    for match in padrao_lista_extenso.finditer(texto):
        mes = MESES[match.group("mes").lower()]
        for dia in _expandir_dias(match.group("dias")):
            _adicionar(resultado, dia, mes, match.group("ano"), match.group(0))
        spans_explicitos.append(match.span())

    # 2. Listas/ranges numéricos: inclusive "de 07 a 09/01".
    padrao_lista_numerica = re.compile(
        r"(?P<dias>\d{1,2}(?:\s*(?:,|e|a|-)\s*\d{1,2})*)"
        r"\s*(?P<sep>[/\-.])\s*(?P<mes>0?[1-9]|1[0-2])"
        r"(?:\s*(?P=sep)\s*(?P<ano>\d{2,4}))?",
        re.I,
    )
    for match in padrao_lista_numerica.finditer(texto):
        for dia in _expandir_dias(match.group("dias")):
            _adicionar(
                resultado, dia, int(match.group("mes")),
                match.group("ano"), match.group(0)
            )
        spans_explicitos.append(match.span())

    # 3. Datas numéricas completas.
    padrao_numerico = re.compile(
        r"\b(?P<dia>0?[1-9]|[12]\d|3[01])\s*"
        r"(?P<sep>[/\-.])\s*(?P<mes>0?[1-9]|1[0-2])\s*"
        r"(?P=sep)\s*(?P<ano>\d{2,4})\b"
    )
    for match in padrao_numerico.finditer(texto):
        if any(
            inicio <= match.start() < fim or inicio < match.end() <= fim
            for inicio, fim in spans_explicitos
        ):
            continue
        _adicionar(
            resultado, match.group("dia"), match.group("mes"),
            match.group("ano"), match.group(0)
        )
        spans_explicitos.append(match.span())

    # 4. Dia/mês sem ano: sempre ano corrente.
    padrao_dia_mes = re.compile(
        r"\b(?P<dia>0?[1-9]|[12]\d|3[01])\s*"
        r"(?P<sep>[/\-.])\s*(?P<mes>0?[1-9]|1[0-2])\b"
        r"(?!\s*(?P=sep)\s*\d{2,4})"
    )
    for match in padrao_dia_mes.finditer(texto):
        if any(
            inicio <= match.start() < fim or inicio < match.end() <= fim
            for inicio, fim in spans_explicitos
        ):
            continue
        _adicionar(
            resultado, match.group("dia"), match.group("mes"),
            None, match.group(0)
        )
        spans_explicitos.append(match.span())

    # 5. "dia 25" / "dias 25 e 26" com mês.
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

    palavras_numero = (
        r"(?:zero|um|uma|dois|duas|três|tres|quatro|cinco|seis|sete|oito|nove|"
        r"dez|onze|doze|treze|quatorze|catorze|quinze|dezesseis|dezasseis|"
        r"dezessete|dezassete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|"
        r"sessenta|setenta|oitenta|noventa|cem|cento|duzentos|duzentas|"
        r"trezentos|trezentas|quatrocentos|quatrocentas|quinhentos|quinhentas|"
        r"seiscentos|seiscentas|setecentos|setecentas|oitocentos|oitocentas|"
        r"novecentos|novecentas|mil)"
    )

    # 6. Data completa por extenso:
    # "sete de janeiro de dois mil e vinte e seis".
    padrao_extenso_completo = re.compile(
        rf"(?P<dia_extenso>{palavras_numero}(?:\s+e\s+{palavras_numero}){{0,3}})"
        rf"\s+de\s+(?P<mes>{MESES_RE})"
        rf"\s+(?:do\s+ano\s+)?de\s+"
        rf"(?P<ano_extenso>{palavras_numero}(?:\s+e\s+{palavras_numero}){{0,8}})",
        re.I,
    )
    for match in padrao_extenso_completo.finditer(texto):
        dia = _numero_por_extenso(match.group("dia_extenso"))
        ano = _numero_por_extenso(match.group("ano_extenso"))
        if dia is not None and ano is not None:
            _adicionar(
                resultado, dia, MESES[match.group("mes").lower()],
                ano, match.group(0)
            )
            spans_explicitos.append(match.span())

    # 7. Dia por extenso + mês, sem ano: sempre ano corrente.
    padrao_extenso_sem_ano = re.compile(
        rf"(?P<dia_extenso>{palavras_numero}(?:\s+e\s+{palavras_numero}){{0,3}})"
        rf"\s+de\s+(?P<mes>{MESES_RE})\b",
        re.I,
    )
    for match in padrao_extenso_sem_ano.finditer(texto):
        if any(
            inicio <= match.start() < fim or inicio < match.end() <= fim
            for inicio, fim in spans_explicitos
        ):
            continue
        dia = _numero_por_extenso(match.group("dia_extenso"))
        if dia is not None:
            _adicionar(
                resultado, dia, MESES[match.group("mes").lower()],
                None, match.group(0)
            )

    resultado.pop("_ano_referencia", None)
    return resultado["datas"]


def encontrar_todas_datas(texto, ano_referencia=None):
    """Retorna todas as datas identificáveis no texto do Ofício.

    Regra do SIEVPM:
      - 07-01-26 / 07/01/26 -> 07/01/2026;
      - 07-01 / 07/01 -> 07/01 do ano corrente;
      - de 07 a 09/01 -> 07/01, 08/01 e 09/01 do ano corrente;
      - 07 de janeiro / sete de janeiro -> 07/01 do ano corrente;
      - sete de janeiro de dois mil e vinte e seis -> 07/01/2026.

    O argumento ano_referencia é mantido por compatibilidade; datas sem ano
    não usam o ano da data preenchida no formulário, e sim o ano corrente.
    """
    datas = _extrair(texto, ano_referencia=ano_referencia)
    return [
        {"texto": texto_original, "data": data}
        for data, texto_original in sorted(datas.items(), key=lambda item: item[0])
    ]
