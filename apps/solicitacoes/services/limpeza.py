from datetime import timedelta

from django.utils import timezone

from apps.solicitacoes.models import Solicitacao


def limpar_documentos_antigos():

    print("=== LIMPEZA DE DOCUMENTOS ===")

    limite = timezone.localdate() - timedelta(days=7)

    solicitacoes = Solicitacao.objects.filter(
        data_evento__lt=limite,
        documentos_expurgados=False
    )

    total = 0

    for s in solicitacoes:

        alterou = False

        print(f"Processando protocolo {s.protocolo}")

        if s.documento_sanitario:
            s.documento_sanitario.delete(save=False)
            s.documento_sanitario = None
            alterou = True
            print("Documento Sanitário removido")

        if s.documento_meio_ambiente:
            s.documento_meio_ambiente.delete(save=False)
            s.documento_meio_ambiente = None
            alterou = True
            print("Documento Meio Ambiente removido")

        if s.oficio_bombeiro:
            s.oficio_bombeiro.delete(save=False)
            s.oficio_bombeiro = None
            alterou = True
            print("Documento Bombeiro removido")

        # Mantém oficio_comandante

        if alterou:

            s.documentos_expurgados = True
            s.save()

            total += 1

    print(
        f"Concluído! {total} solicitações tiveram os documentos temporários removidos."
    )

    return total
