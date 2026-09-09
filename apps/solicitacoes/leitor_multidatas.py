from .documentos_otimizados import extrair_texto_pdf_rapido
from .leitor_datas_robusto import encontrar_todas_datas


def detectar_datas_oficio(arquivo_pdf, ano_referencia=None):
    """Extrai e identifica datas sem executar OCR redundante."""
    arquivo_pdf.seek(0)
    texto = extrair_texto_pdf_rapido(arquivo_pdf)
    arquivo_pdf.seek(0)

    return encontrar_todas_datas(
        texto,
        ano_referencia=ano_referencia,
    )
