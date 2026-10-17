import logging

from .pesquisas import enviar_pesquisas_pendentes
from .limpeza import limpar_documentos_antigos


logger = logging.getLogger(__name__)


def executar_rotina_diaria():
    """Executa as duas tarefas uma vez, sem deixar uma falha impedir a outra."""
    logger.info("===== ROTINA DIÁRIA SiEv: início =====")
    erros = []

    try:
        enviados = enviar_pesquisas_pendentes()
        logger.info("Pesquisas enviadas nesta execução: %s", enviados)
    except Exception:
        logger.exception("Falha ao enviar pesquisas pendentes.")
        erros.append("envio de pesquisas")

    try:
        removidos = limpar_documentos_antigos()
        logger.info("Solicitações com documentos complementares removidos: %s", removidos)
    except Exception:
        logger.exception("Falha na limpeza de documentos antigos.")
        erros.append("limpeza de documentos")

    logger.info("===== ROTINA DIÁRIA SiEv: fim =====")

    if erros:
        raise RuntimeError("Falha(s) na rotina diária: " + ", ".join(erros))
