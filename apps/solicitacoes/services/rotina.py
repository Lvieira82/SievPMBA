from .pesquisas import enviar_pesquisas_pendentes
from .limpeza import limpar_documentos_antigos


def executar_rotina_diaria():
    print("===== ROTINA DIÁRIA =====")

    enviar_pesquisas_pendentes()

    limpar_documentos_antigos()

    print("===== FIM DA ROTINA =====")
