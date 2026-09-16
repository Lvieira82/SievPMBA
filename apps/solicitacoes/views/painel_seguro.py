from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from apps.solicitacoes.models import Solicitacao
from apps.solicitacoes.permissoes import (
    eh_desenvolvedor,
    eh_membro_unidade,
    escopo_unidades,
    pode_cadastrar_usuario,
    pode_gerar_opo,
    pode_lancamento_manual,
    pode_ver_administracao,
    pode_ver_documentacao_solicitacao,
    pode_ver_historico,
    pode_ver_mapa_eventos,
    pode_ver_proximos_eventos,
    pode_ver_ranking,
    perfil_gestor,
)


@login_required
def painel_gestao_seguro(request):
    hoje = timezone.localdate()
    if eh_desenvolvedor(request.user):
        base = Solicitacao.objects.all()
        nivel = "DESENVOLVEDOR"
        titulo = "Administração do Sistema"
    else:
        unidades = escopo_unidades(request.user)
        if not unidades.exists():
            messages.error(request, "Usuário sem escopo institucional válido.")
            return redirect("login_gestao")
        base = Solicitacao.objects.filter(unidade__in=unidades)
        a = request.user.acesso_institucional
        nivel = a.perfil
        titulo = str(a.unidade) if a.unidade_id else str(a.cpr) if a.cpr_id else a.get_perfil_display()

    return render(request, "gestao/painel_gestao.html", {
        "perfil": getattr(request.user, "acesso_institucional", None),
        "nivel": nivel,
        "titulo_painel": titulo,
        "eh_desenvolvedor": eh_desenvolvedor(request.user),
        "eh_membro_unidade": eh_membro_unidade(request.user),
        "pode_administrar": pode_ver_administracao(request.user),
        "pode_proximos": pode_ver_proximos_eventos(request.user),
        "pode_historico": pode_ver_historico(request.user),
        "pode_analise": pode_ver_ranking(request.user),
        "pode_mapa": pode_ver_mapa_eventos(request.user),
        "pode_documentacao": pode_ver_documentacao_solicitacao(request.user),
        "pode_gerar_opo": pode_gerar_opo(request.user),
        "pode_manual": pode_lancamento_manual(request.user),
        "pode_cadastrar_usuario": pode_cadastrar_usuario(request.user),
        "pode_pesquisas": perfil_gestor(request.user, "COPPM"),
        "pendentes_opo": base.filter(status="PENDENTE").count(),
        "eventos_semana": base.filter(data_evento__range=[hoje, hoje + timedelta(days=7)]).count(),
        "eventos_mes": base.filter(data_evento__year=hoje.year, data_evento__month=hoje.month).count(),
        "proximos_eventos": base.filter(data_evento__gte=hoje).order_by("data_evento", "hora_inicio")[:5],
        "usuarios": request.user.__class__.objects.count(),
    })
