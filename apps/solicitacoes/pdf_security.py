from django.core.exceptions import ValidationError

import fitz


MAX_PDF_SIZE = 10 * 1024 * 1024


def validar_pdf_upload(arquivo, max_size=MAX_PDF_SIZE):
    """Valida o conteúdo do arquivo, não apenas sua extensão."""
    if not arquivo:
        raise ValidationError("Arquivo PDF não informado.")

    tamanho = getattr(arquivo, "size", None)
    if tamanho is not None and tamanho > max_size:
        raise ValidationError(
            "O PDF excede o limite de 10 MB."
        )

    arquivo.seek(0)
    cabecalho = arquivo.read(5)
    arquivo.seek(0)

    if cabecalho != b"%PDF-":
        raise ValidationError(
            "O arquivo enviado não possui uma assinatura PDF válida."
        )

    try:
        conteudo = arquivo.read()
        with fitz.open(stream=conteudo, filetype="pdf") as documento:
            if len(documento) == 0:
                raise ValidationError("O PDF não possui páginas.")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            "O arquivo enviado não é um PDF válido."
        ) from exc
    finally:
        arquivo.seek(0)

    return arquivo
