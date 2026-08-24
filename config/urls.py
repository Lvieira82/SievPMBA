from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from apps.solicitacoes.views.administracao import (
    usuarios_unidade,
    cadastrar_usuario_unidade,
    login_gestao,
    logout_gestao,
    painel_gestao,

    editar_usuario_unidade,
    trocar_senha_usuario,
    desativar_usuario_unidade,

    aprovacoes,
    aprovar_solicitacao,
    solicitar_correcao_gestao,
    transferir_solicitacao,
)
from apps.solicitacoes.views.dashboard import (
    dashboard,
    eventos_hoje,
    proximos_eventos_gestao,
    por_municipio,
    por_unidade,
    por_tipo,
    calendario,
    mapa,
    listar_pendentes_opo,
)
from apps.solicitacoes.portal_views import (portal,
    selecionar_unidade,listar_unidades, lista_municipios, nova_solicitacao, corrigir_solicitacao,
    )
from apps.solicitacoes.views import (

    minhas_solicitacoes,
    consultar_protocolo,
    verificar_autenticidade,
    alterar_status,
    documentos_solicitacao,
    abrir_documento_solicitacao,
    agenda_gestao,
    lancamento_manual,
    opos_geradas,
    detalhe_opo,
    gerar_opo,
    validar_matricula_opo_publica,
    detalhe_opo_publica,
    importar_matriculas_painel,
    corrigir_solicitacao,
    mapa_eventos,
    gerar_mapa_eventos_pdf,
    importar_municipios,
    eventos_dia, eventos_dia_resultado, 
)

urlpatterns = [
    # ==========================================================
    # GESTÃO DE USUÁRIOS
    # ==========================================================

    path(
        "gestao/usuarios/",
        usuarios_unidade,
        name="usuarios_unidade",
    ),

    path(
        "gestao/usuarios/cadastrar/",
        cadastrar_usuario_unidade,
        name="cadastrar_usuario_unidade",
    ),
    path(
        "gestao/pendentes-opo/",
        listar_pendentes_opo,
        name="listar_pendentes_opo",
    ),    

    path(
        "gestao/usuarios/<int:id>/editar/",
        editar_usuario_unidade,
        name="editar_usuario_unidade",
    ),

    path(
        "gestao/usuarios/<int:id>/senha/",
        trocar_senha_usuario,
        name="trocar_senha_usuario",
    ),

    path(
        "gestao/usuarios/<int:id>/desativar/",
        desativar_usuario_unidade,
        name="desativar_usuario_unidade",
    ),
    path(
        "gestao/usuarios/",
        usuarios_unidade,
        name="usuarios_unidade",
    ),
        path(
        "eventos-do-dia/",
        eventos_dia,
        name="eventos_dia",
    ),

    path(
        "eventos-do-dia/resultado/",
        eventos_dia_resultado,
        name="eventos_dia_resultado",
    ),

    path(
        "gestao/usuarios/cadastrar/",
        cadastrar_usuario_unidade,
        name="cadastrar_usuario_unidade",
    ),
    path(
        "api/unidades/<int:cpr_id>/",
        listar_unidades,
        name="listar_unidades",
    ),
    path(
        "api/municipios/",
        lista_municipios,
        name="lista_municipios"
    ),
    path(
        "",
        portal,
        name="portal"
    ),
    path(
        "gestao/importar-municipios/",
        importar_municipios,
        name="importar_municipios",
    ),
    
    path(
        "portal/entrar/",
        selecionar_unidade,
        name="selecionar_unidade",
    ),
    path("admin/", admin.site.urls),
    path(
        "painel_gestao/importar-matriculas/",
        importar_matriculas_painel,
        name="importar_matriculas_painel"
    ),
    path(
        "documento/<int:id>/<str:tipo>/",
        abrir_documento_solicitacao,
        name="abrir_documento_solicitacao",
    ),

    path(
        "gestao/lancamento-manual/",
        lancamento_manual,
        name="lancamento_manual",
    ),
    path(
        "gestao/mapa-eventos/",
        mapa_eventos,
        name="mapa_eventos"
    ),
    
    path(
        "gestao/mapa-eventos/pdf/",
        gerar_mapa_eventos_pdf,
        name="gerar_mapa_eventos_pdf"
    ),
    path(
        "gestao/opos-geradas/",
        opos_geradas,
        name="opos_geradas",
    ),

    path(
        "gestao/opo/<int:id>/detalhes/",
        detalhe_opo,
        name="detalhe_opo",
    ),
    path(
        "corrigir/<str:protocolo>/",
        corrigir_solicitacao,
        name="corrigir_solicitacao"
    ),
   
    
    path("gestao/", login_gestao, name="login_gestao"),

    path("logout/", logout_gestao, name="logout_gestao"),

    path(
        "painel/",
        painel_gestao,
        name="painel_gestao",
    ),
    path(
        "solicitacao/<int:id>/corrigir/",
        solicitar_correcao_gestao,
        name="solicitar_correcao"
    ),

    path(
        "consultar/",
        consultar_protocolo,
        name="consultar",
    ),

    path(
        "documentos/<int:id>/",
        documentos_solicitacao,
        name="documentos_solicitacao",
    ),

    path(
        "nova/",
        nova_solicitacao,
        name="nova_solicitacao",
    ),
    path(
        "consulta/opo/<int:id>/matricula/",
        validar_matricula_opo_publica,
        name="validar_matricula_opo_publica"
    ),
    path(
        "consulta/opo/<int:id>/detalhes/",
        detalhe_opo_publica,
        name="detalhe_opo_publica"
    ),

    path(
        "minhas/",
        minhas_solicitacoes,
        name="minhas_solicitacoes",
    ),

    path(
        "dashboard/",
        dashboard,
        name="dashboard",
    ),
   
    path(
        "verificar/<str:protocolo>/",
        verificar_autenticidade,
        name="verificar_autenticidade",
    ),

    path(
        "alterar-status/<int:id>/<str:status>/",
        alterar_status,
        name="alterar_status",
    ),

    path(
        "aprovar/<int:id>/",
        aprovar_solicitacao,
        name="aprovar_solicitacao",
    ),

    path(
        "opo/<int:id>/",
        gerar_opo,
        name="gerar_opo",
    ),
    

    path(
        "aprovacoes/",
        aprovacoes,
        name="aprovacoes",
    ),
    path(
        "aprovacoes/transferir/<int:id>/",
        transferir_solicitacao,
        name="transferir_solicitacao",
    ),
    path(
        "gestao/proximos-eventos/",
        proximos_eventos_gestao,
        name="proximos_eventos_gestao",
    ),
    
    path(
        "gestao/agenda/",
        agenda_gestao,
        name="agenda_gestao",
    ),
    # Servir arquivos da pasta media
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
