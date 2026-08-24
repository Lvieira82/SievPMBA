from django.urls import path
from .views import (
    nova_solicitacao,
    minhas_solicitacoes,
    dashboard_operacional,
    verificar_autenticidade,
    alterar_status,
    aprovar_solicitacao,
  
)

urlpatterns = [
    path('nova/', nova_solicitacao, name='nova_solicitacao'),
    path('minhas/', minhas_solicitacoes, name='minhas_solicitacoes'),
    path('dashboard/', dashboard_operacional, name='dashboard_operacional'),
    path('verificar/<str:protocolo>/', verificar_autenticidade, name='verificar_autenticidade'),

    path(
        'alterar-status/<int:id>/<str:status>/',
        alterar_status,
        name='alterar_status'
    ),

    path(
        'aprovar/<int:id>/',
        aprovar_solicitacao,
        name='aprovar_solicitacao'
    ),

]