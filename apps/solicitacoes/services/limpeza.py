from django.utils import timezone


def limpar_documentos_antigos():
    """
    Rotina de compatibilidade.

    O modelo Solicitacao atualmente não possui os campos de expurgo usados
    pela rotina antiga (documentos_expurgados, documento_sanitario,
    documento_meio_ambiente e oficio_bombeiro). Não executamos exclusões
    especulativas de documentos até que essa regra seja novamente definida
    no modelo.
    """
    print("=== LIMPEZA DE DOCUMENTOS ===")
    print(
        "Limpeza de documentos temporariamente desativada: "
        "o modelo atual não possui os campos de expurgo da rotina antiga."
    )
    print(f"Verificação executada em {timezone.localtime():%d/%m/%Y %H:%M:%S}.")
    return 0
