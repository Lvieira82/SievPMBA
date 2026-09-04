from .utils import extrair_texto_pdf, encontrar_datas_no_texto


def detectar_datas_oficio(arquivo_pdf, ano_referencia=None):
    """Extrai e identifica todas as datas presentes no Ofício.

    A leitura é feita pelo mesmo motor PDF/OCR já existente no projeto.
    A regra de antecedência não pertence ao leitor: ela é aplicada pelo
    fluxo de solicitação, depois que todas as datas são identificadas.
    """
    arquivo_pdf.seek(0)
    texto = extrair_texto_pdf(arquivo_pdf)
    arquivo_pdf.seek(0)

    datas = encontrar_datas_no_texto(texto)

    if ano_referencia:
        # Mantém apenas o parâmetro por compatibilidade futura; o leitor
        # não deve filtrar datas por proximidade nem pela data X.
        pass

    return sorted(datas, key=lambda item: item["data"])
