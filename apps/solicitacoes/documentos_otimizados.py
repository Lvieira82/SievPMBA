import io
import re
from datetime import date, datetime

import fitz
import pytesseract
from django.core.files.base import ContentFile
from PIL import Image

from .leitor_datas_robusto import encontrar_todas_datas


OCR_DPI = 140
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
    """OCR de uma unica pagina, em escala de cinza e uma so passagem."""
    pixmap = pagina.get_pixmap(
        dpi=OCR_DPI,
        colorspace=fitz.csGRAY,
        alpha=False,
    )
    imagem = Image.open(io.BytesIO(pixmap.tobytes("png")))
    try:
        texto = pytesseract.image_to_string(
            imagem,
            lang="por",
            config="--oem 3 --psm 6",
            timeout=35,
        )
    finally:
        try:
            imagem.close()
        except Exception:
            pass
        del pixmap
    return _normalizar(texto)


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
    Valida a data do oficio com estrategia em duas etapas:

    1. texto digital da primeira pagina;
    2. OCR somente se a data esperada nao puder ser confirmada.

    Isso evita renderizar/OCRizar paginas que nao participam da validacao.
    """
    arquivo_pdf.seek(0)
    conteudo = arquivo_pdf.read()
    texto = ""
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
            texto = _normalizar(pagina.get_text("text"))
            datas = encontrar_todas_datas(
                texto,
                ano_referencia=getattr(data_evento, "year", None),
            )

            data_alvo_encontrada = any(item["data"] == data_evento for item in datas)

            # OCR somente quando o texto digital nao confirma a data.
            if not data_alvo_encontrada:
                try:
                    texto_ocr = _ocr_pagina(pagina)
                except Exception as erro:
                    print("LEITOR DATAS - OCR indisponivel/falhou:", repr(erro))
                    texto_ocr = ""

                if texto_ocr:
                    texto = f"{texto}\n{texto_ocr}" if texto else texto_ocr
                    datas = encontrar_todas_datas(
                        texto,
                        ano_referencia=getattr(data_evento, "year", None),
                    )
    finally:
        arquivo_pdf.seek(0)

    datas_normalizadas = {item["data"] for item in datas}
    return {
        "valido": data_evento in datas_normalizadas,
        "datas": datas,
        "datas_normalizadas": sorted(datas_normalizadas),
        "multiplas_datas": len(datas_normalizadas) >= 2,
        "texto_extraido": texto,
    }


def extrair_texto_pdf_rapido(arquivo_pdf):
    """
    Extrai texto do PDF sem OCR em paginas digitais.
    Em paginas escaneadas, executa uma unica passagem de OCR por pagina.
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
                    print(f"LEITOR DATAS - ERRO OCR PAGINA {numero}:", repr(erro))
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
    Compacta PDF para armazenamento em grande volume.

    Primeiro aplica compactacao estrutural sem perda. Se o arquivo continuar
    grande, reduz imagens embutidas para 140 DPI/qualidade 70, preservando
    a camada de texto e a estrutura das paginas.
    """
    if not arquivo:
        return arquivo

    arquivo.seek(0)
    original = arquivo.read()
    original_size = len(original)
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

            # So faz a etapa com perda quando ela tem potencial real de economia.
            if len(compactado) > original_size * 0.70 and hasattr(doc, "rewrite_images"):
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
        print("PDF COMPACTACAO - FALHA, mantendo original:", repr(erro))
        arquivo.seek(0)
        return arquivo
    finally:
        arquivo.seek(0)
