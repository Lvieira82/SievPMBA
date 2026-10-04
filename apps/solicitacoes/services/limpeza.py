from datetime import timedelta

from django.utils import timezone

from apps.solicitacoes.models import Solicitacao, DocumentoSolicitacao


def limpar_documentos_antigos():
    """Remove documentos complementares antigos sem acessar campos inexistentes.

    O modelo atual armazena os documentos em DocumentoSolicitacao. O código
    anterior ainda tentava acessar campos legados que não existem mais em
    Solicitacao (documentos_expurgados, documento_sanitario etc.), fazendo a
    rotina diária falhar com FieldError.

    O Ofício ao Comandante é preservado, conforme a regra histórica da rotina.
    """
    print("=== LIMPEZA DE DOCUMENTOS ===")

    limite = timezone.localdate() - timedelta(days=7)
    solicitacoes = Solicitacao.objects.filter(data_evento__lt=limite).only("id", "protocolo")

    total = 0
    for solicitacao in solicitacoes:
        documentos = DocumentoSolicitacao.objects.filter(solicitacao=solicitacao).exclude(
            tipo_documento__nome__iexact="Ofício ao Comandante"
        )

        quantidade = documentos.count()
        if quantidade:
            print(f"Processando protocolo {solicitacao.protocolo}: {quantidade} documento(s)")
            documentos.delete()
            total += 1

    print(f"Concluído! {total} solicitações tiveram documentos complementares antigos removidos.")
    return total
