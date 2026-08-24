import os
from io import BytesIO
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from pathlib import Path
import re
import io
import unicodedata
from datetime import datetime
import fitz
import dateparser
import pytesseract
from PIL import Image
import unicodedata



def gerar_qrcode(protocolo):

    pasta = (
        Path(settings.MEDIA_ROOT)
        / "qrcodes"
    )

    pasta.mkdir(
        parents=True,
        exist_ok=True
    )

    url = (
        f"http://127.0.0.1:8000/"
        f"verificar/{protocolo}/"
    )

    img = qrcode.make(url)

    arquivo = pasta / f"{protocolo}.png"

    img.save(arquivo)

    return arquivo
def gerar_pdf_autorizacao(solicitacao):

    pasta = os.path.join(
        settings.MEDIA_ROOT,
        'autorizacoes'
    )

    os.makedirs(pasta, exist_ok=True)

    nome_arquivo = (
        f'AUTORIZACAO_{solicitacao.protocolo}.pdf'
    )

    caminho = os.path.join(
        pasta,
        nome_arquivo
    )

    c = canvas.Canvas(caminho, pagesize=A4)

    largura, altura = A4

    c.setFont("Helvetica-Bold", 18)

    c.drawString(
        150,
        altura - 80,
        "AUTORIZAÇÃO DE POLICIAMENTO"
    )

    c.setFont("Helvetica", 12)

    y = altura - 140

    dados = [

        f"Protocolo: {solicitacao.protocolo}",

        f"Evento: {solicitacao.nome_evento}",

        f"Solicitante: {solicitacao.solicitante}",

        f"Data do Evento: {solicitacao.data_evento}",

        f"Horário: {solicitacao.hora_inicio} às {solicitacao.hora_fim}",

        f"Local: {solicitacao.local}",

        f"Público estimado: {solicitacao.publico_estimado}",

        f"Status: {solicitacao.status}",

    ]

    for item in dados:

        c.drawString(80, y, item)

        y -= 25

    c.drawString(
        80,
        y - 40,
        f"Assinado digitalmente por:"
    )

    c.drawString(
        80,
        y - 65,
        f"{solicitacao.assinado_por or 'COMANDO'}"
    )

    c.drawString(
        80,
        y - 90,
        f"Data assinatura: {solicitacao.data_assinatura}"
    )

    url_validacao = (
        f"http://127.0.0.1:8000/verificar/{solicitacao.protocolo}/"
    )

    qr = qrcode.make(url_validacao)

    buffer = BytesIO()

    qr.save(buffer)

    buffer.seek(0)

    qr_image = ImageReader(buffer)

    c.drawImage(
        qr_image,
        420,
        80,
        width=120,
        height=120
    )

    c.drawString(
        380,
        60,
        "Validar autenticidade"
    )

    c.save()

    return nome_arquivo




# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

MESES_PT = (
    r"janeiro|fevereiro|março|marco|abril|maio|junho|"
    r"julho|agosto|setembro|outubro|novembro|dezembro"
)

# Quantidade mínima de caracteres para considerar
# que a página possui texto digital aproveitável.
MINIMO_CARACTERES_TEXTO = 30

# Resolução utilizada no OCR.
OCR_DPI = 150


# ==========================================================
# NORMALIZAÇÃO DO TEXTO
# ==========================================================

def normalizar_texto(texto):
    """
    Normaliza espaços e caracteres do texto extraído.

    Mantém os acentos para facilitar a identificação
    de datas por extenso em português.
    """

    if not texto:
        return ""

    texto = texto.replace("\u00a0", " ")

    # Remove espaços repetidos
    texto = re.sub(
        r"[ \t]+",
        " ",
        texto
    )

    # Reduz excesso de linhas vazias
    texto = re.sub(
        r"\n\s*\n+",
        "\n",
        texto
    )

    return texto.strip()


# ==========================================================
# OCR DA PÁGINA
# ==========================================================

def aplicar_ocr_na_pagina(pagina):
    """
    Converte uma página do PDF em imagem e executa OCR.

    Utilizado quando o PDF não possui texto digital
    suficiente para ser analisado.
    """

    pixmap = pagina.get_pixmap(
        dpi=OCR_DPI,
        colorspace=fitz.csGRAY,
        alpha=False
    )

    imagem = Image.open(
        io.BytesIO(
            pixmap.tobytes("png")
        )
    )

    texto = pytesseract.image_to_string(
        imagem,
        lang="por",
        config="--oem 3 --psm 6"
    )

    return normalizar_texto(texto)


# ==========================================================
# EXTRAÇÃO COMPLETA DO PDF
# ==========================================================

def extrair_texto_pdf(arquivo_pdf):
    """
    Extrai texto de PDFs digitais e PDFs escaneados.

    1. Tenta extrair texto normalmente com PyMuPDF.
    2. Se houver pouco texto, usa OCR.
    3. Reposiciona o arquivo no início.
    """

    texto_completo = []

    arquivo_pdf.seek(0)

    conteudo = arquivo_pdf.read()

    try:

        with fitz.open(
            stream=conteudo,
            filetype="pdf"
        ) as documento:

            for numero_pagina, pagina in enumerate(
                documento,
                start=1
            ):

                texto_digital = normalizar_texto(
                    pagina.get_text("text")
                )

                # PDF digital
                if len(texto_digital) >= MINIMO_CARACTERES_TEXTO:

                    texto_pagina = texto_digital

                # PDF escaneado
                else:

                    try:

                        texto_pagina = aplicar_ocr_na_pagina(
                            pagina
                        )

                    except Exception as erro_ocr:

                        print(
                            f"ERRO DE OCR NA PÁGINA "
                            f"{numero_pagina}: {erro_ocr}"
                        )

                        texto_pagina = texto_digital

                if texto_pagina:
                    texto_completo.append(
                        texto_pagina
                    )

    finally:

        # Muito importante:
        # permite que o Django continue salvando o arquivo.
        arquivo_pdf.seek(0)

    return "\n".join(texto_completo)


# ==========================================================
# NORMALIZAÇÃO DO ANO
# ==========================================================

def normalizar_ano_curto(data):
    """
    Converte anos com dois dígitos.

    Exemplos:

    15/08/26 -> 15/08/2026
    15/08/99 -> 15/08/1999
    """

    if data.year < 100:

        ano_atual = datetime.now().year

        ano_atual_curto = ano_atual % 100

        if data.year <= ano_atual_curto + 20:

            ano_completo = 2000 + data.year

        else:

            ano_completo = 1900 + data.year

        return data.replace(
            year=ano_completo
        )

    return data


# ==========================================================
# CORREÇÃO DE ERROS DO OCR
# ==========================================================

def corrigir_erros_ocr_em_datas(texto):
    """
    Corrige espaços introduzidos pelo OCR em datas.

    Exemplos:

    15 / 08 / 2026
    15/ 08/2026
    15 - 08 - 2026

    tornam-se:

    15/08/2026
    15-08-2026
    """

    if not texto:
        return ""

    texto = re.sub(
        r"(\d{1,2})\s*([/\-.])\s*(\d{1,2})\s*\2\s*(\d{2,4})",
        r"\1\2\3\2\4",
        texto
    )

    return texto


# ==========================================================
# LOCALIZAÇÃO DAS DATAS
# ==========================================================

def encontrar_datas_no_texto(texto):
    """
    Procura datas no texto do Ofício.

    Aceita:

        15/08/2026
        15/08/26
        15-08-2026
        15.08.2026

    e:

        15 de agosto de 2026
        15 de agosto do ano de 2026

    Retorna somente datas únicas.
    """

    texto = corrigir_erros_ocr_em_datas(
        texto
    )

    datas_encontradas = []

    datas_normalizadas = set()


    # ======================================================
    # 1. DATAS NUMÉRICAS
    # ======================================================

    padrao_numerico = re.compile(
        r"\b"
        r"(?:0?[1-9]|[12]\d|3[01])"
        r"\s*[\/\-.]\s*"
        r"(?:0?[1-9]|1[0-2])"
        r"\s*[\/\-.]\s*"
        r"(?:\d{2}|\d{4})"
        r"\b"
    )

    for correspondencia in padrao_numerico.finditer(
        texto
    ):

        data_original = correspondencia.group(0)

        # Remove espaços inseridos pelo OCR
        data_para_parse = re.sub(
            r"\s+",
            "",
            data_original
        )

        data_convertida = dateparser.parse(
            data_para_parse,
            languages=["pt"],
            settings={
                "DATE_ORDER": "DMY",
                "STRICT_PARSING": True,
            }
        )

        if not data_convertida:
            continue

        data_convertida = normalizar_ano_curto(
            data_convertida
        )

        data_final = data_convertida.date()

        if data_final not in datas_normalizadas:

            datas_normalizadas.add(
                data_final
            )

            datas_encontradas.append({
                "texto": data_original,
                "data": data_final,
            })


    # ======================================================
    # 2. DATAS POR EXTENSO
    # ======================================================

    padrao_extenso = re.compile(
        rf"\b"
        rf"(?:0?[1-9]|[12]\d|3[01])"
        rf"\s+de\s+"
        rf"(?:{MESES_PT})"
        rf"(?:\s+do\s+ano)?"
        rf"\s+de\s+"
        rf"\d{{4}}"
        rf"\b",
        re.IGNORECASE
    )

    for correspondencia in padrao_extenso.finditer(
        texto
    ):

        data_original = correspondencia.group(0)

        # Exemplo:
        #
        # 15 de agosto do ano de 2026
        #
        # vira:
        #
        # 15 de agosto de 2026

        texto_para_parse = re.sub(
            r"\s+do\s+ano\s+de\s+",
            " de ",
            data_original,
            flags=re.IGNORECASE
        )

        data_convertida = dateparser.parse(
            texto_para_parse,
            languages=["pt"],
            settings={
                "DATE_ORDER": "DMY",
                "STRICT_PARSING": True,
            }
        )

        if not data_convertida:
            continue

        data_final = data_convertida.date()

        if data_final not in datas_normalizadas:

            datas_normalizadas.add(
                data_final
            )

            datas_encontradas.append({
                "texto": data_original,
                "data": data_final,
            })


    return datas_encontradas


# ==========================================================
# ANÁLISE FINAL DO OFÍCIO
# ==========================================================

def analisar_datas_oficio(arquivo_pdf, data_evento):
    """
    Analisa a primeira página do Ofício ao Comandante.

    Processo:

    1. Abre o PDF.
    2. Verifica se existe página.
    3. Tenta extrair texto digital.
    4. Se o texto for insuficiente, utiliza OCR.
    5. Procura todas as datas.
    6. Compara as datas encontradas com a data do evento.
    7. Retorna o resultado da validação.
    """

    arquivo_pdf.seek(0)

    conteudo = arquivo_pdf.read()

    try:

        with fitz.open(
            stream=conteudo,
            filetype="pdf"
        ) as documento:

            # ==================================================
            # PDF SEM PÁGINAS
            # ==================================================

            if len(documento) == 0:

                return {
                    "valido": False,
                    "datas": [],
                    "datas_normalizadas": [],
                    "multiplas_datas": False,
                    "texto_extraido": "",
                }


            # ==================================================
            # PRIMEIRA PÁGINA
            # ==================================================

            pagina = documento[0]


            # ==================================================
            # PRIMEIRO TENTA TEXTO DIGITAL
            # ==================================================

            texto = normalizar_texto(
                pagina.get_text("text")
            )


            # ==================================================
            # SE NÃO CONSEGUIU, USA OCR
            # ==================================================

            if len(texto) < MINIMO_CARACTERES_TEXTO:

                try:

                    texto = aplicar_ocr_na_pagina(
                        pagina
                    )

                except Exception as erro:

                    print(
                        "ERRO OCR NO OFÍCIO:",
                        repr(erro)
                    )

                    texto = ""


    finally:

        # Fundamental para o Django continuar
        # trabalhando com o UploadedFile.
        arquivo_pdf.seek(0)


    # ==================================================
    # ENCONTRA DATAS
    # ==================================================

    datas = encontrar_datas_no_texto(
        texto
    )


    # ==================================================
    # NORMALIZA DATAS ENCONTRADAS
    # ==================================================

    datas_normalizadas = {
        item["data"]
        for item in datas
    }


    # ==================================================
    # VERIFICA SE A DATA DO EVENTO EXISTE NO OFÍCIO
    # ==================================================

    data_confere = (
        data_evento in datas_normalizadas
    )


    # ==================================================
    # VERIFICA MÚLTIPLAS DATAS
    # ==================================================

    multiplas_datas = (
        len(datas_normalizadas) >= 2
    )


    # ==================================================
    # RETORNO
    # ==================================================

    return {

        "valido": data_confere,

        "datas": datas,

        "datas_normalizadas": sorted(
            datas_normalizadas
        ),

        "multiplas_datas": multiplas_datas,

        "texto_extraido": texto,
    }