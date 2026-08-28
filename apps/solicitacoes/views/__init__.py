"""Exports públicos das views do SiEv."""

from ..portal_views import (
    agenda_gestao, consultar_protocolo, corrigir_solicitacao, lista_bairros,
    lista_municipios, listar_unidades, listar_pendentes_opo, nova_solicitacao,
    portal, proximos_eventos_gestao, selecionar_unidade,
)
from .acesso import (
    esqueci_senha, logout_gestao, redefinir_senha, trocar_senha_primeiro_acesso,
    verificar_novo_navegador,
)
from .login_institucional import login_gestao
from .gestao_acesso import (
    administracao_sistema, usuario_novo, usuario_editar, usuario_senha,
    usuario_desativar, transferir_solicitacao_segura,
)
from .administracao import (
    aprovacoes, aprovar_solicitacao, backup, bairros, cprs, configuracoes,
    municipios, obter_perfil_gestor, painel_administracao, painel_gestao,
    solicitar_correcao_gestao, tipos_documento, tipos_evento, unidades,
    usuarios,
)
from .analise import (
    aprovar, detalhes, estatisticas, fila_analise, historico, indeferir,
    painel_analise, solicitar_correcao,
)
from .compat import (
    alterar_status, detalhe_opo, detalhe_opo_publica, documentos_solicitacao,
    gerar_mapa_eventos_pdf, gerar_opo, importar_matriculas_painel,
    importar_municipios, lancamento_manual, mapa_eventos, minhas_solicitacoes,
    opos_geradas, validar_matricula_opo_publica, verificar_autenticidade,
    abrir_documento_solicitacao,
)
from .dashboard import (
    calendario, dashboard, eventos_hoje, mapa, por_municipio, por_tipo,
    por_unidade,
)
from .eventos import eventos_dia, eventos_dia_resultado
from .protocolo import (
    cancelar_protocolo, detalhes_protocolo, encaminhar_unidade,
    estatisticas_protocolo, fila_protocolo, historico_protocolo,
    painel_protocolo, reenviar_email,
)
usuarios_unidade=administracao_sistema
cadastrar_usuario_unidade=usuario_novo
editar_usuario_unidade=usuario_editar
trocar_senha_usuario=usuario_senha
desativar_usuario_unidade=usuario_desativar
transferir_solicitacao=transferir_solicitacao_segura
