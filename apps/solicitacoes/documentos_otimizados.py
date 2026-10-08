import io
import re
from datetime import date, datetime

import fitz
import pytesseract
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .leitor_datas_robusto import encontrar_todas_datas


OCR_DPI = 220
MINIMO_TEXTO_DIGITAL = 30
MAX_PAGINA_OCR = 1


def _normalizar(texto):
    if not texto:
        return ""
    texto = texto.replace("\u00a0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n", texto)
    return texto.strip()


def _ocr_pagina(pagina):
    """OCR de uma única página com pré-processamento para documentos administrativos.

    O Tesseract é usado somente quando a camada de texto digital não basta.
    A imagem é ampliada e recebe autocontraste antes do OCR, mantendo o
    reconhecimento em português e evitando configurações voltadas a caracteres
    isolados que podem piorar a leitura de datas.
    """
    pixmap = pagina.get_pixmap(
        dpi=OCR_DPI,
        colorspace=fitz.csGRAY,
        alpha=False,
    )
    imagem = Image.open(io.BytesIO(pixmap.tobytes("png")))
    try:
        imagem = ImageOps.autocontrast(imagem)
        texto = pytesseract.image_to_string(
            imagem,
            lang="por",
            config="--oem 1 --psm 6 -c preserve_interword_spaces=1",
            timeout=35,
        )
    finally:
        try:
            imagem.close()
        except Exception:
            pass
        del pixmap
    return _normalizar(texto)


def _remover_data_de_emissao(texto):
    """Remove a data de emissão/cabeçalho antes da validação de eventos.

    Ex.: 'Salvador, 03 de setembro de 2026.' não é uma data de evento.
    A remoção é feita apenas no fluxo de validação do Ofício; o leitor geral
    continua capaz de identificar essa data quando necessário.
    """
    if not texto:
        return ""

    linhas = texto.splitlines()
    padrao_emissao = re.compile(
        rf"^\s*[^\n,]+,\s*"
        rf"(?:0?[1-9]|[12]\\d|3[01])\s+de\s+"
        rf"(?:{__import__('apps.solicitacoes.leitor_datas_robusto', fromlist=['MESES_RE']).MESES_RE})"
        rf"\s+(?:de\s+)?(?:\d{{2,4}})\s*\.?\s*$",
        re.I,
    )
    linhas_filtradas = []
    removida = False
    for linha in linhas:
        if not removida and padrao_emissao.match(linha):
            removida = True
            continue
        linhas_filtradas.append(linha)
    return "\n".join(linhas_filtradas)


def extrair_primeira_pagina_rapida(arquivo_pdf):
    """Le somente a primeira pagina, evitando OCR desnecessario no restante."""
    arquivo_pdf.seek(0)
    conteudo = arquivo_pdf.read()
    try:
        with fitz.open(stream=conteudo, filetype="pdf") as documento:
            if not documento:
                return ""
            return _normalizar(documento[0].get_text("text"))
    finally:
        arquivo_pdf.seek(0)


def analisar_datas_oficio_rapido(arquivo_pdf, data_evento):
    """
    Valida a data do Ofício priorizando a camada de texto digital.

    Em PDF digital, não executa OCR quando a data informada já foi encontrada.
    Se precisar de OCR, o resultado do OCR não substitui nem polui a lista de
    datas digitais. Em PDF escaneado, o OCR é usado como fonte principal.

    A data de emissão do cabeçalho (ex.: 'Salvador, 03 de setembro de 2026')
    é retirada da lista de datas de evento.
    """
    arquivo_pdf.seek(0)
    conteudo = arquivo_pdf.read()
    texto = ""
    datas = []
    texto_digital = ""

    try:
        with fitz.open(stream=conteudo, filetype="pdf") as documento:
            if not documento:
                return {
                    "valido": False,
                    "datas": [],
                    "datas_normalizadas": [],
                    "multiplas_datas": False,
                    "texto_extraido": "",
                }

            pagina = documento[0]
            texto_digital = _normalizar(pagina.get_text("text"))
            texto_digital_evento = _remover_data_de_emissao(texto_digital)
            texto = texto_digital

            datas_digitais = encontrar_todas_datas(
                texto_digital_evento,
                ano_referencia=getattr(data_evento, "year", None),
            )

            data_alvo_encontrada = any(
                item["data"] == data_evento for item in datas_digitais
            )

            if data_alvo_encontrada:
                datas = datas_digitais
            else:
                try:
                    texto_ocr = _ocr_pagina(pagina)
                except Exception as erro:
                    print(
                        "LEITOR DATAS - OCR indisponível/falhou:",
                        repr(erro),
                    )
                    texto_ocr = ""

                texto_ocr_evento = _remover_data_de_emissao(texto_ocr)
                datas_ocr = (
                    encontrar_todas_datas(
                        texto_ocr_evento,
                        ano_referencia=getattr(data_evento, "year", None),
                    )
                    if texto_ocr_evento
                    else []
                )

                if texto_ocr:
                    texto = (
                        f"{texto_digital}\n{texto_ocr}"
                        if texto_digital
                        else texto_ocr
                    )

                if not texto_digital.strip():
                    datas = datas_ocr
                elif any(item["data"] == data_evento for item in datas_ocr):
                    # Em PDF digital, OCR só pode confirmar a data solicitada.
                    # As demais datas continuam vindo do texto digital.
                    datas = list(datas_digitais)
                    if not any(item["data"] == data_evento for item in datas):
                        datas.append(
                            next(
                                item
                                for item in datas_ocr
                                if item["data"] == data_evento
                            )
                        )
                else:
                    datas = datas_digitais

    finally:
        arquivo_pdf.seek(0)

    datas_normalizadas = {item["data"] for item in datas}
    return {
        "valido": data_evento in datas_normalizadas,
        "datas": sorted(datas, key=lambda item: item["data"]),
        "datas_normalizadas": sorted(datas_normalizadas),
        "multiplas_datas": len(datas_normalizadas) >= 2,
        "texto_extraido": texto,
    }

