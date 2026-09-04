from .utils import extrair_texto_pdf
from .leitor_datas_robusto import encontrar_todas_datas


def detectar_datas_oficio(arquivo_pdf, ano_referencia=None):
    """Extrai e identifica todas as datas presentes no Ofício.

    A leitura aceita formatos numéricos, datas por extenso, listas de dias,
    intervalos e combinações desses formatos. O leitor somente identifica as
    datas; a regra de antecedência continua sendo aplicada pelo fluxo de
    solicitação.
    """
    arquivo_pdf.seek(0)
    texto = extrair_texto_pdf(arquivo_pdf)
    arquivo_pdf.seek(0)

    return encontrar_todas_datas(
        texto,
        ano_referencia=ano_referencia,
    )
