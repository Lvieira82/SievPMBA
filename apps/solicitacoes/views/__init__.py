"""Exports públicos das views do SiEv.

Cada função é importada explicitamente do módulo que realmente a implementa.
Isso evita que funções placeholder sobrescrevam views reais durante imports.
"""

from ..portal_views import (
    agenda_gestao,
    consultar_protocolo,
    corrigir_solicitacao,
    lista_bairros,
    lista_municipios,
    listar_unidades,
    listar_pendentes_opo,
    nova_solicitacao,
    portal,
    proximos_eventos_gestao,
    selecionar_unidade,
)
from .administracao import (
    aprovacoes,
    aprovar_solicitacao,
    backup,
    bairros,
    cadastrar_usuario_unidade,
    configuracoes,
    cprs,
    desativar_usuario_unidade,
    editar_usuario_unidade,
    login_gestao,
    logout_gestao,
    municipios,
    obter_perfil_gestor,
    painel_administracao,
    painel_gestao,
    solicitar_correcao_gestao,
    tipos_documento,
    tipos_evento,
    transferir_solicitacao,
    trocar_senha_usuario,
    unidades,
    usuarios,
    usuarios_unidade,
)
from .analise import (
    aprovar,
    detalhes,
    estatisticas,
    fila_analise,
    historico,
    indeferir,
    painel_analise,
    solicitar_correcao,
)
from .compat import (
    alterar_status,
    detalhe_opo,
    detalhe_opo_publica,
    documentos_solicitacao,
    gerar_mapa_eventos_pdf,
    gerar_opo,
    importar_matriculas_painel,
    importar_municipios,
    lancamento_manual,
    mapa_eventos,
    minhas_solicitacoes,
    opos_geradas,
    validar_matricula_opo_publica,
    verificar_autenticidade,
    abrir_documento_solicitacao,
)
from .dashboard import (
    calendario,
    dashboard,
    eventos_hoje,
    mapa,
    por_municipio,
    por_tipo,
    por_unidade,
)
from .eventos import eventos_dia, eventos_dia_resultado
from .protocolo import (
    cancelar_protocolo,
    detalhes_protocolo,
    encaminhar_unidade,
    estatisticas_protocolo,
    fila_protocolo,
    historico_protocolo,
    painel_protocolo,
    reenviar_email,
)

# O fluxo abaixo é específico da conferência documental do operador.
# Estas importações ficam por último de propósito para substituir as
# versões antigas exportadas pelos módulos de compatibilidade/gestão.
from .documentos_operador import (
    aprovacoes,
    aprovar_solicitacao,
    documentos_solicitacao,
)
