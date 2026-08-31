"""Compatibilidade das rotas antigas com as views operacionais reais."""

from .manual import lancamento_manual
from .minhas import minhas_solicitacoes
from .operacional import (
    alterar_status,
    detalhe_opo_publica,
    documentos_solicitacao,
    importar_matriculas_painel,
    importar_municipios,
    validar_matricula_opo_publica,
    verificar_autenticidade,
    abrir_documento_solicitacao,
)
from .escopo_operacional import (
    detalhe_opo,
    gerar_mapa_eventos_pdf,
    gerar_opo,
    mapa_eventos,
    opos_geradas,
)
