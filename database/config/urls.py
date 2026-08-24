from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from solicitacoes.views import (
    home,
    nova_solicitacao,
    minhas_solicitacoes,
    consultar_protocolo,
    dashboard_operacional,
    verificar_autenticidade,
    alterar_status,
    aprovar_solicitacao,
    gerar_pdf,
    login_gestao,
    logout_gestao,
    painel_gestao,
)


urlpatterns = [
    path('gestao/', login_gestao, name='login_gestao'),
    path('logout/', logout_gestao, name='logout_gestao'),
    path('admin/', admin.site.urls),
    path(
    'consultar/',
    consultar_protocolo,
    name='consultar_protocolo'
),
    # HOME
    path('', home, name='home'),
    
    path(
    'painel/',
    painel_gestao,
    name='painel_gestao'
),
    # SOLICITAÇÕES
    path('nova/', nova_solicitacao, name='nova_solicitacao'),
    path('minhas/', minhas_solicitacoes, name='minhas_solicitacoes'),
    path('dashboard/', dashboard_operacional, name='dashboard_operacional'),

    # AÇÕES
    path('verificar/<str:protocolo>/', verificar_autenticidade, name='verificar_autenticidade'),
    path('alterar-status/<int:id>/<str:status>/', alterar_status, name='alterar_status'),
    path('aprovar/<int:id>/', aprovar_solicitacao, name='aprovar_solicitacao'),
    path('gerar-pdf/<int:id>/', gerar_pdf, name='gerar_pdf'),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

