"""Compatibilidade das rotas antigas com as views operacionais reais."""

from .manual import lancamento_manual
from .minhas import minhas_solicitacoes
from .operacional import (
    alterar_status,
    detalhe_opo,
    detalhe_opo_publica,
    documentos_solicitacao,
    gerar_mapa_eventos_pdf,
    gerar_opo,
    importar_matriculas_painel,
    importar_municipios,
    mapa_eventos,
    opos_geradas,
    validar_matricula_opo_publica,
    verificar_autenticidade,
    abrir_documento_solicitacao,
)
