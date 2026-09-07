import os

from django.conf import settings
from django.contrib import admin
from django.urls import path
from django.views.static import serve
from django.contrib.staticfiles.views import serve as serve_static
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect

from apps.solicitacoes.portal_views import (
    consultar_protocolo, corrigir_solicitacao, lista_bairros,
    lista_municipios, listar_unidades, nova_solicitacao, portal,
    selecionar_unidade,
)
from apps.solicitacoes.portal_views_multiplas import nova_solicitacao, confirmar_multiplas
from apps.solicitacoes.views.administracao import (
    cadastrar_usuario_unidade, desativar_usuario_unidade, editar_usuario_unidade,
    logout_gestao, trocar_senha_usuario, usuarios_unidade,
)
from apps.solicitacoes.views.login_acesso import login_gestao
from apps.solicitacoes.views.acesso import (
    logout_gestao as logout_gestao_seguro, esqueci_senha, redefinir_senha,
    trocar_senha_primeiro_acesso, verificar_novo_navegador,
)
from apps.solicitacoes.views.administracao_sistema import (
    administracao_sistema, usuario_desativar, usuario_editar, usuario_novo, usuario_senha,
)
from apps.solicitacoes.views.administracao_acoes import usuario_ativar, usuario_excluir
from apps.solicitacoes.views.administracao_unidade_membro import (
    administracao_unidade_membro, editar_operador_membro,
    ativar_operador_membro, desativar_operador_membro, excluir_operador_membro,
)
from apps.solicitacoes.views.cadastro_territorio import (
    cadastro_bairros, cadastro_unidades, editar_bairro, editar_unidade,
    ativar_bairro, desativar_bairro, excluir_bairro,
    ativar_unidade, desativar_unidade, excluir_unidade,
)
from apps.solicitacoes.views.compat import (
    alterar_status, importar_matriculas_painel, importar_municipios, lancamento_manual,
    minhas_solicitacoes, verificar_autenticidade,
)
from apps.solicitacoes.views.public_opo import abrir_opo_publica, detalhe_opo_publica, validar_matricula_opo_publica
from apps.solicitacoes.views.dashboard import dashboard
from apps.solicitacoes.views.analise import analise_unidades
from apps.solicitacoes.views.eventos import eventos_dia, eventos_dia_resultado
from apps.solicitacoes.views.painel_acesso import painel_gestao
from apps.solicitacoes.views.cumprimento_opo import cumprimento_opo, abrir_opo_operador
from apps.solicitacoes.views.agenda_gestao_segura import agenda_gestao_segura, proximos_eventos_gestao_seguro
from apps.solicitacoes.views.protocolo import (
    cancelar_protocolo, detalhes_protocolo, encaminhar_unidade, estatisticas_protocolo,
    fila_protocolo, historico_protocolo, painel_protocolo, reenviar_email,
)
from apps.solicitacoes.views.territorio_admin import (
    areas_responsabilidade, editar_area_responsabilidade,
    ativar_area_responsabilidade, desativar_area_responsabilidade,
    excluir_area_responsabilidade, bairros_por_municipio,
    importar_areas_responsabilidade,
)
from apps.solicitacoes.views.aprovacoes_seguras import (
    aprovacoes, aprovar_solicitacao, solicitar_correcao_gestao,
)
from apps.solicitacoes.views.escopo_gestao import (
    documentos_solicitacao_seguro, abrir_documento_solicitacao_seguro,
    abrir_oficio_comandante_seguro, abrir_opo_gestao_seguro,
    opos_geradas_seguro, detalhe_opo_seguro, mapa_eventos_seguro,
    gerar_opo_seguro,
)
from apps.solicitacoes.views.mapa_eventos_pdf import gerar_mapa_eventos_pdf_seguro
from apps.solicitacoes.views.transferencia_segura import transferir_solicitacao_seguro
from apps.solicitacoes.views.apoio_operacional import (
    enviar_apoio, apoios_recebidos, abrir_apoio, gerar_opo_apoio,
)
from apps.solicitacoes.permissoes import pode_gerar_opo


@login_required
def listar_pendentes_opo_seguro(request):
    if not pode_gerar_opo(request.user):
        messages.error(request, "Somente o Gestor de Unidade pode acessar a geração de OPO nesta etapa.")
        return redirect("painel_gestao")
    return aprovacoes(request)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", portal, name="portal"),
    path("portal/entrar/", selecionar_unidade, name="selecionar_unidade"),
    path("nova/", nova_solicitacao, name="nova_solicitacao"),
    path("confirmar-datas/", confirmar_multiplas, name="confirmar_datas"),
    path("consultar/", consultar_protocolo, name="consultar"),
    path("corrigir/<str:protocolo>/", corrigir_solicitacao, name="corrigir_solicitacao"),
    path("api/municipios/", lista_municipios, name="lista_municipios"),
    path("api/municipios/<int:municipio_id>/bairros/", lista_bairros, name="lista_bairros"),
    path("api/unidades/<int:cpr_id>/", listar_unidades, name="listar_unidades"),
    path("api/gestao/municipios/<int:municipio_id>/bairros/", bairros_por_municipio, name="bairros_por_municipio"),
    path("eventos-do-dia/", eventos_dia, name="eventos_dia"),
    path("eventos-do-dia/resultado/", eventos_dia_resultado, name="eventos_dia_resultado"),
    path("eventos-do-dia/cumprimento/<int:solicitacao_id>/", cumprimento_opo, name="cumprimento_opo"),
    path("eventos-do-dia/opo/arquivo/<int:anexo_id>/", abrir_opo_operador, name="abrir_opo_operador"),
    path("gestao/", login_gestao, name="login_gestao"),
    path("gestao/verificar-navegador/", verificar_novo_navegador, name="verificar_novo_navegador"),
    path("gestao/esqueci-senha/", esqueci_senha, name="esqueci_senha"),
    path("gestao/redefinir-senha/<uidb64>/<token>/", redefinir_senha, name="redefinir_senha"),
    path("gestao/primeiro-acesso/senha/", trocar_senha_primeiro_acesso, name="trocar_senha_primeiro_acesso"),
    path("logout/", logout_gestao_seguro, name="logout_gestao"),
    path("painel/", painel_gestao, name="painel_gestao"),
    path("gestao/analise/", analise_unidades, name="analise_unidades"),
    path("gestao/administracao/", administracao_sistema, name="administracao_sistema"),
    path("gestao/administracao/unidade-membro/", administracao_unidade_membro, name="administracao_unidade_membro"),
    path("gestao/administracao/unidade-membro/operador/<int:id>/editar/", editar_operador_membro, name="editar_operador_membro"),
    path("gestao/administracao/unidade-membro/operador/<int:id>/ativar/", ativar_operador_membro, name="ativar_operador_membro"),
    path("gestao/administracao/unidade-membro/operador/<int:id>/desativar/", desativar_operador_membro, name="desativar_operador_membro"),
    path("gestao/administracao/unidade-membro/operador/<int:id>/excluir/", excluir_operador_membro, name="excluir_operador_membro"),
    path("gestao/administracao/usuario/novo/", usuario_novo, name="administracao_usuario_novo"),
    path("gestao/administracao/usuario/<int:id>/editar/", usuario_editar, name="administracao_usuario_editar"),
    path("gestao/administracao/usuario/<int:id>/senha/", usuario_senha, name="administracao_usuario_senha"),
    path("gestao/administracao/usuario/<int:id>/desativar/", usuario_desativar, name="administracao_usuario_desativar"),
    path("gestao/administracao/usuario/<int:id>/ativar/", usuario_ativar, name="administracao_usuario_ativar"),
    path("gestao/administracao/usuario/<int:id>/excluir/", usuario_excluir, name="administracao_usuario_excluir"),
    path("gestao/cadastro/unidades/", cadastro_unidades, name="cadastro_unidades"),
    path("gestao/cadastro/unidades/<int:id>/editar/", editar_unidade, name="editar_unidade"),
    path("gestao/cadastro/unidades/<int:id>/ativar/", ativar_unidade, name="ativar_unidade"),
    path("gestao/cadastro/unidades/<int:id>/desativar/", desativar_unidade, name="desativar_unidade"),
    path("gestao/cadastro/unidades/<int:id>/excluir/", excluir_unidade, name="excluir_unidade"),
    path("gestao/cadastro/bairros/", cadastro_bairros, name="cadastro_bairros"),
    path("gestao/cadastro/bairros/<int:id>/editar/", editar_bairro, name="editar_bairro"),
    path("gestao/cadastro/bairros/<int:id>/ativar/", ativar_bairro, name="ativar_bairro"),
    path("gestao/cadastro/bairros/<int:id>/desativar/", desativar_bairro, name="desativar_bairro"),
    path("gestao/cadastro/bairros/<int:id>/excluir/", excluir_bairro, name="excluir_bairro"),
    path("gestao/usuarios/", usuarios_unidade, name="usuarios_unidade"),
    path("gestao/usuarios/cadastrar/", cadastrar_usuario_unidade, name="cadastrar_usuario_unidade"),
    path("gestao/usuarios/<int:id>/editar/", editar_usuario_unidade, name="editar_usuario_unidade"),
    path("gestao/usuarios/<int:id>/senha/", trocar_senha_usuario, name="trocar_senha_usuario"),
    path("gestao/usuarios/<int:id>/desativar/", desativar_usuario_unidade, name="desativar_usuario_unidade"),
    path("gestao/areas-responsabilidade/", areas_responsabilidade, name="areas_responsabilidade"),
    path("gestao/areas-responsabilidade/<int:id>/editar/", editar_area_responsabilidade, name="editar_area_responsabilidade"),
    path("gestao/areas-responsabilidade/<int:id>/ativar/", ativar_area_responsabilidade, name="ativar_area_responsabilidade"),
    path("gestao/areas-responsabilidade/<int:id>/desativar/", desativar_area_responsabilidade, name="desativar_area_responsabilidade"),
    path("gestao/areas-responsabilidade/<int:id>/excluir/", excluir_area_responsabilidade, name="excluir_area_responsabilidade"),
    path("gestao/areas-responsabilidade/importar/", importar_areas_responsabilidade, name="importar_areas_responsabilidade"),
    path("gestao/pendentes-opo/", listar_pendentes_opo_seguro, name="listar_pendentes_opo"),
    path("aprovacoes/", aprovacoes, name="aprovacoes"),
    path("aprovar/<int:id>/", aprovar_solicitacao, name="aprovar_solicitacao"),
    path("aprovacoes/transferir/<int:id>/", transferir_solicitacao_seguro, name="transferir_solicitacao"),
    path("solicitacao/<int:id>/corrigir/", solicitar_correcao_gestao, name="solicitar_correcao"),
    path("gestao/proximos-eventos/", proximos_eventos_gestao_seguro, name="proximos_eventos_gestao"),
    path("gestao/agenda/", agenda_gestao_segura, name="agenda_gestao"),
    path("dashboard/", dashboard, name="dashboard"),
    path("dashboard/operacional/", dashboard, name="dashboard_operacional"),
    path("minhas/", minhas_solicitacoes, name="minhas_solicitacoes"),
    path("verificar/<str:protocolo>/", verificar_autenticidade, name="verificar_autenticidade"),
    path("alterar-status/<int:id>/<str:status>/", alterar_status, name="alterar_status"),
    path("documentos/<int:id>/", documentos_solicitacao_seguro, name="documentos_solicitacao"),
    path("documento/oficio/<int:id>/", abrir_oficio_comandante_seguro, name="abrir_oficio_comandante"),
    path("documento/<int:id>/<str:tipo>/", abrir_documento_solicitacao_seguro, name="abrir_documento_solicitacao"),
    path("documento/<int:id>/", abrir_documento_solicitacao_seguro, name="abrir_documento_solicitacao_direto"),
    path("documentos/arquivo/<int:id>/", abrir_documento_solicitacao_seguro, name="abrir_documento_arquivo"),
    path("gestao/lancamento-manual/", lancamento_manual, name="lancamento_manual"),
    path("gestao/mapa-eventos/", mapa_eventos_seguro, name="mapa_eventos"),
    path("gestao/mapa-eventos/pdf/", gerar_mapa_eventos_pdf_seguro, name="gerar_mapa_eventos_pdf"),
    path("gestao/opos-geradas/", opos_geradas_seguro, name="opos_geradas"),
    path("gestao/opo/<int:id>/detalhes/", detalhe_opo_seguro, name="detalhe_opo"),
    path("gestao/opo/arquivo/<int:anexo_id>/", abrir_opo_gestao_seguro, name="abrir_opo_gestao"),
    path("opo/<int:id>/", gerar_opo_seguro, name="gerar_opo"),
    path("gestao/opo/<int:id>/apoio/", enviar_apoio, name="enviar_apoio"),
    path("gestao/apoios/", apoios_recebidos, name="apoios_recebidos"),
    path("gestao/apoio/<int:id>/", abrir_apoio, name="abrir_apoio"),
    path("gestao/apoio/<int:id>/gerar-opo/", gerar_opo_apoio, name="gerar_opo_apoio"),
    path("consulta/opo/<int:id>/matricula/", validar_matricula_opo_publica, name="validar_matricula_opo_publica"),
    path("consulta/opo/<int:id>/detalhes/", detalhe_opo_publica, name="detalhe_opo_publica"),
    path("consulta/opo/<int:id>/arquivo/", abrir_opo_publica, name="abrir_opo_publica"),
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

if os.environ.get("RENDER") != "true":
    urlpatterns += [path("static/<path:path>", serve_static)]

if settings.DEBUG:
    urlpatterns += [path("media/<path:path>", serve, {"document_root": settings.MEDIA_ROOT})]
