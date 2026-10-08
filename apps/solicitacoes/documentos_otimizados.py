import io
import re
from datetime import date, datetime

import fitz
import pytesseract
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .leitor_datas_robusto import MESES_RE, encontrar_todas_datas


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
        rf"(?:0?[1-9]|[12]\d|3[01])\s+de\s+"
        rf"(?:{MESES_RE})\s+(?:de\s+)?(?:\d{{2,4}})",
        re.I,
    )
    linhas_filtradas = []
    removida = False

    for indice, linha in enumerate(linhas):
        # A data de emissão normalmente aparece no início do Ofício,
        # antes do corpo: "Salvador, 03 de setembro de 2026.".
        # Removemos somente essa ocorrência inicial, nunca datas do corpo.
        if (
            not removida
            and indice < 5
            and "," in linha
            and padrao_emissao.search(linha)
        ):
            removida = True
            linha = padrao_emissao.sub("", linha, count=1)
            linha = re.sub(r"^[,\s]+|[,\s]+$", "", linha)
            if linha.strip():
                linhas_filtradas.append(linha)
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

def extrair_texto_pdf_rapido(arquivo_pdf):
    """
    Extrai texto do PDF sem OCR em páginas digitais.
    Em páginas escaneadas, executa uma única passagem de OCR por página.
    """
    arquivo_pdf.seek(0)
    conteudo = arquivo_pdf.read()
    partes = []
    try:
        with fitz.open(stream=conteudo, filetype="pdf") as documento:
            for numero, pagina in enumerate(documento, start=1):
                digital = _normalizar(pagina.get_text("text"))
                if len(digital) >= MINIMO_TEXTO_DIGITAL:
                    partes.append(digital)
                    continue
                try:
                    ocr = _ocr_pagina(pagina)
                except Exception as erro:
                    print(
                        f"LEITOR DATAS - ERRO OCR PAGINA {numero}:",
                        repr(erro),
                    )
                    ocr = ""
                if ocr:
                    partes.append(ocr)
                elif digital:
                    partes.append(digital)
    finally:
        arquivo_pdf.seek(0)
    return "\n".join(partes)


def compactar_pdf_upload(arquivo, nome=None):
    """
    Compacta o PDF antes do armazenamento, preservando a camada de texto.
    A compactação com perda só é aplicada quando há ganho relevante.
    """
    if not arquivo:
        return arquivo

    arquivo.seek(0)
    original = arquivo.read()
    original_size = len(original)

    # PDFs pequenos não precisam passar por regravação.
    if original_size < 150 * 1024:
        arquivo.seek(0)
        return arquivo

    try:
        doc = fitz.open(stream=original, filetype="pdf")
        try:
            saida = io.BytesIO()
            doc.save(
                saida,
                garbage=3,
                deflate=True,
                deflate_images=True,
                deflate_fonts=True,
                use_objstms=1,
            )
            compactado = saida.getvalue()

            # Só reduz imagens quando a compactação estrutural não foi suficiente.
            if (
                len(compactado) > original_size * 0.70
                and hasattr(doc, "rewrite_images")
            ):
                doc.rewrite_images(
                    dpi_threshold=180,
                    dpi_target=140,
                    quality=70,
                    lossy=True,
                    lossless=True,
                    bitonal=True,
                    color=True,
                    gray=True,
                )
                saida2 = io.BytesIO()
                doc.save(
                    saida2,
                    garbage=3,
                    deflate=True,
                    deflate_images=True,
                    deflate_fonts=True,
                    use_objstms=1,
                )
                compactado2 = saida2.getvalue()
                if len(compactado2) < len(compactado):
                    compactado = compactado2
        finally:
            doc.close()

        if len(compactado) >= original_size:
            arquivo.seek(0)
            return arquivo

        nome_final = nome or getattr(arquivo, "name", "documento.pdf")
        resultado = ContentFile(compactado, name=nome_final)
        print(
            "PDF COMPACTADO:",
            original_size,
            "->",
            len(compactado),
            "bytes",
        )
        return resultado
    except Exception as erro:
        print(
            "PDF COMPACTACAO - FALHA, mantendo original:",
            repr(erro),
        )
        arquivo.seek(0)
        return arquivo
    finally:
        arquivo.seek(0)

