from django.conf import settings
from django.contrib import admin
from django.urls import path
from django.views.static import serve

from apps.solicitacoes.portal_views import (
    agenda_gestao, consultar_protocolo, corrigir_solicitacao, lista_bairros,
    lista_municipios, listar_unidades, listar_pendentes_opo, nova_solicitacao,
    portal, proximos_eventos_gestao, selecionar_unidade,
)
from apps.solicitacoes.views.administracao import (
    aprovacoes, aprovar_solicitacao, cadastrar_usuario_unidade,
    desativar_usuario_unidade, editar_usuario_unidade, login_gestao,
    logout_gestao, painel_gestao, solicitar_correcao_gestao,
    transferir_solicitacao, trocar_senha_usuario, usuarios_unidade,
)
from apps.solicitacoes.views.administracao_sistema import (
    administracao_sistema, usuario_desativar, usuario_editar,
    usuario_novo, usuario_senha,
)
from apps.solicitacoes.views.compat import (
    alterar_status, detalhe_opo, detalhe_opo_publica, documentos_solicitacao,
    gerar_mapa_eventos_pdf, gerar_opo, importar_matriculas_painel,
    importar_municipios, lancamento_manual, mapa_eventos, minhas_solicitacoes,
    opos_geradas, validar_matricula_opo_publica, verificar_autenticidade,
    abrir_documento_solicitacao,
)
from apps.solicitacoes.views.dashboard import dashboard
from apps.solicitacoes.views.analise import analise_unidades
from apps.solicitacoes.views.eventos import eventos_dia, eventos_dia_resultado
from apps.solicitacoes.views.protocolo import (
    cancelar_protocolo, detalhes_protocolo, encaminhar_unidade,
    estatisticas_protocolo, fila_protocolo, historico_protocolo,
    painel_protocolo, reenviar_email,
)
from apps.solicitacoes.views.territorio_admin import (
    areas_responsabilidade, bairros_por_municipio,
    importar_areas_responsabilidade,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", portal, name="portal"),
    path("portal/entrar/", selecionar_unidade, name="selecionar_unidade"),
    path("nova/", nova_solicitacao, name="nova_solicitacao"),
    path("consultar/", consultar_protocolo, name="consultar"),
    path("corrigir/<str:protocolo>/", corrigir_solicitacao, name="corrigir_solicitacao"),
    path("api/municipios/", lista_municipios, name="lista_municipios"),
    path("api/municipios/<int:municipio_id>/bairros/", lista_bairros, name="lista_bairros"),
    path("api/unidades/<int:cpr_id>/", listar_unidades, name="listar_unidades"),
    path("api/gestao/municipios/<int:municipio_id>/bairros/", bairros_por_municipio, name="bairros_por_municipio"),
    path("eventos-do-dia/", eventos_dia, name="eventos_dia"),
    path("eventos-do-dia/resultado/", eventos_dia_resultado, name="eventos_dia_resultado"),
    path("gestao/", login_gestao, name="login_gestao"),
    path("logout/", logout_gestao, name="logout_gestao"),
    path("painel/", painel_gestao, name="painel_gestao"),
    path("gestao/analise/", analise_unidades, name="analise_unidades"),
    path("gestao/administracao/", administracao_sistema, name="administracao_sistema"),
    path("gestao/administracao/usuario/novo/", usuario_novo, name="administracao_usuario_novo"),
    path("gestao/administracao/usuario/<int:id>/editar/", usuario_editar, name="administracao_usuario_editar"),
    path("gestao/administracao/usuario/<int:id>/senha/", usuario_senha, name="administracao_usuario_senha"),
    path("gestao/administracao/usuario/<int:id>/desativar/", usuario_desativar, name="administracao_usuario_desativar"),
    path("gestao/usuarios/", usuarios_unidade, name="usuarios_unidade"),
    path("gestao/usuarios/cadastrar/", cadastrar_usuario_unidade, name="cadastrar_usuario_unidade"),
    path("gestao/usuarios/<int:id>/editar/", editar_usuario_unidade, name="editar_usuario_unidade"),
    path("gestao/usuarios/<int:id>/senha/", trocar_senha_usuario, name="trocar_senha_usuario"),
    path("gestao/usuarios/<int:id>/desativar/", desativar_usuario_unidade, name="desativar_usuario_unidade"),
    path("gestao/areas-responsabilidade/", areas_responsabilidade, name="areas_responsabilidade"),
    path("gestao/areas-responsabilidade/importar/", importar_areas_responsabilidade, name="importar_areas_responsabilidade"),
    path("gestao/pendentes-opo/", listar_pendentes_opo, name="listar_pendentes_opo"),
    path("aprovacoes/", aprovacoes, name="aprovacoes"),
    path("aprovar/<int:id>/", aprovar_solicitacao, name="aprovar_solicitacao"),
    path("aprovacoes/transferir/<int:id>/", transferir_solicitacao, name="transferir_solicitacao"),
    path("solicitacao/<int:id>/corrigir/", solicitar_correcao_gestao, name="solicitar_correcao"),
    path("gestao/proximos-eventos/", proximos_eventos_gestao, name="proximos_eventos_gestao"),
    path("gestao/agenda/", agenda_gestao, name="agenda_gestao"),
    path("dashboard/", dashboard, name="dashboard"),
    path("dashboard/operacional/", dashboard, name="dashboard_operacional"),
    path("minhas/", minhas_solicitacoes, name="minhas_solicitacoes"),
    path("verificar/<str:protocolo>/", verificar_autenticidade, name="verificar_autenticidade"),
    path("alterar-status/<int:id>/<str:status>/", alterar_status, name="alterar_status"),
    path("documentos/<int:id>/", documentos_solicitacao, name="documentos_solicitacao"),
    path("documento/<int:id>/<str:tipo>/", abrir_documento_solicitacao, name="abrir_documento_solicitacao"),
    path("gestao/lancamento-manual/", lancamento_manual, name="lancamento_manual"),
    path("gestao/mapa-eventos/", mapa_eventos, name="mapa_eventos"),
    path("gestao/mapa-eventos/pdf/", gerar_mapa_eventos_pdf, name="gerar_mapa_eventos_pdf"),
    path("gestao/opos-geradas/", opos_geradas, name="opos_geradas"),
    path("gestao/opo/<int:id>/detalhes/", detalhe_opo, name="detalhe_opo"),
    path("opo/<int:id>/", gerar_opo, name="gerar_opo"),
    path("consulta/opo/<int:id>/matricula/", validar_matricula_opo_publica, name="validar_matricula_opo_publica"),
    path("consulta/opo/<int:id>/detalhes/", detalhe_opo_publica, name="detalhe_opo_publica"),
    path("painel_gestao/importar-matriculas/", importar_matriculas_painel, name="importar_matriculas_painel"),
    path("gestao/importar-municipios/", importar_municipios, name="importar_municipios"),
    path("protocolo/", painel_protocolo, name="painel_protocolo"),
    path("protocolo/fila/", fila_protocolo, name="fila_protocolo"),
    path("protocolo/<int:pk>/", detalhes_protocolo, name="detalhes_protocolo"),
    path("protocolo/<int:pk>/encaminhar/", encaminhar_unidade, name="encaminhar_unidade"),
    path("protocolo/<int:pk>/historico/", historico_protocolo, name="historico_protocolo"),
    path("protocolo/<int:pk>/reenviar-email/", reenviar_email, name="reenviar_email"),
    path("protocolo/<int:pk>/cancelar/", cancelar_protocolo, name="cancelar_protocolo"),
    path("protocolo/estatisticas/", estatisticas_protocolo, name="estatisticas_protocolo"),
]

if settings.DEBUG:
    urlpatterns += [path("media/<path:path>", serve, {"document_root": settings.MEDIA_ROOT})]
