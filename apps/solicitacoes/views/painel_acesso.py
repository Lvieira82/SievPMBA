from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.solicitacoes.models import Solicitacao, PerfilUsuario
from apps.solicitacoes.permissoes import (
    acesso_do_usuario,
    descricao_acesso,
    eh_desenvolvedor,
    eh_operador,
    eh_gestor,
    eh_membro,
    eh_membro_unidade,
    escopo_unidades,
    pode_ver_administracao,
    pode_cadastrar_operador,
    pode_ver_historico,
    pode_ver_ranking,
    pode_ver_proximos_eventos,
    pode_ver_mapa_eventos,
    pode_ver_dashboard,
    pode_ver_documentacao_solicitacao,
    pode_gerar_opo,
    pode_lancamento_manual,
)


@login_required
def painel_gestao(request):
    user = request.user

    if eh_operador(user):
        return redirect("eventos_dia")

    if not eh_desenvolvedor(user) and not acesso_do_usuario(user):
        messages.error(request, "Usuário sem acesso institucional válido.")
        return redirect("login_gestao")

    unidades = escopo_unidades(user)
    if eh_desenvolvedor(user):
        solicitacoes = Solicitacao.objects.all()
        titulo = "Administração do Sistema"
        nivel = "DESENVOLVEDOR"
    else:
        acesso = acesso_do_usuario(user)
        solicitacoes = Solicitacao.objects.filter(unidade__in=unidades)
        if acesso.perfil == "COPPM":
            titulo = "Gestão COPPM" if acesso.funcao == "GESTOR" else "Acesso COPPM"
        elif acesso.perfil == "CPR":
            titulo = f"Gestão {acesso.cpr}" if acesso.funcao == "GESTOR" else f"Acesso {acesso.cpr}"
        elif acesso.perfil == "UNIDADE":
            titulo = f"Gestão {acesso.unidade}" if acesso.funcao == "GESTOR" else f"Acesso {acesso.unidade}"
        else:
            titulo = "Acesso institucional"
        nivel = acesso.perfil

    hoje = timezone.localdate()
    acesso = acesso_do_usuario(user)

    context = {
        "perfil": acesso,
        "nivel": nivel,
        "funcao": "DESENVOLVEDOR" if eh_desenvolvedor(user) else acesso.funcao,
        "titulo_painel": titulo,
        "descricao_acesso": descricao_acesso(user),
        "eh_desenvolvedor": eh_desenvolvedor(user),
        "eh_gestor": eh_gestor(user),
        "eh_membro": eh_membro(user),
        "eh_membro_unidade": eh_membro_unidade(user),
        "eh_operador": eh_operador(user),
        "pode_administrar": pode_ver_administracao(user),
        "pode_cadastrar_operador": pode_cadastrar_operador(user),
        "pode_proximos": pode_ver_proximos_eventos(user),
        "pode_historico": pode_ver_historico(user),
        "pode_analise": pode_ver_ranking(user),
        "pode_mapa": pode_ver_mapa_eventos(user),
        "pode_dashboard": pode_ver_dashboard(user),
        "pode_documentacao": pode_ver_documentacao_solicitacao(user),
        "pode_gerar_opo": bool(pode_gerar_opo(user)),
        "pode_manual": pode_lancamento_manual(user),
        "pendentes_opo": solicitacoes.filter(status="PENDENTE").count(),
        "eventos_semana": solicitacoes.filter(data_evento__gte=hoje, data_evento__lte=hoje + timedelta(days=7)).count(),
        "eventos_mes": solicitacoes.filter(data_evento__year=hoje.year, data_evento__month=hoje.month).count(),
        "proximos_eventos": solicitacoes.filter(data_evento__gte=hoje).select_related("unidade", "municipio", "bairro").order_by("data_evento", "hora_inicio")[:5],
        "usuarios": 0 if eh_desenvolvedor(user) else None,
    }

    if eh_desenvolvedor(user):
        context["usuarios"] = __import__("django.contrib.auth.models", fromlist=["User"]).User.objects.count()
    else:
        context["usuarios"] = __import__("apps.solicitacoes.models_acesso", fromlist=["AcessoInstitucional"]).AcessoInstitucional.objects.filter(ativo=True).count()

    return render(request, "gestao/painel_gestao.html", context)
