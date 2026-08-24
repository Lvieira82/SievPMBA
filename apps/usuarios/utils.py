import os
from io import BytesIO
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from pathlib import Path


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