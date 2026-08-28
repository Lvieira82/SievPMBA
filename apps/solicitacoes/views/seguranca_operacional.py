from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao, Unidade
from apps.solicitacoes.permissoes import pode_aprovar_solicitacao, pode_lancamento_manual, pode_transferir, pode_ver_solicitacao, escopo_unidades
from .operacional import lancamento_manual as manual_original

@login_required
def lancamento_manual_seguro(request):
    if not pode_lancamento_manual(request.user):
        messages.error(request,"Você não possui permissão para criar OPO manual."); return redirect("painel_gestao")
    return manual_original(request)

@login_required
def aprovacoes_seguras(request):
    return __import__("apps.solicitacoes.views.administracao",fromlist=["aprovacoes"]).aprovacoes.__wrapped__(request) if False else __import__("django.shortcuts",fromlist=["render"]).render(request,"gestao/aprovacoes.html",{"solicitacoes":Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user)).select_related("unidade","municipio","tipo_evento").order_by("data_evento","hora_inicio")})

@login_required
def aprovar_solicitacao_segura(request,id):
    if request.method!="POST": return redirect("aprovacoes")
    s=get_object_or_404(Solicitacao.objects.select_related("unidade"),pk=id)
    if not pode_aprovar_solicitacao(request.user,s): messages.error(request,"Você não possui acesso a esta solicitação."); return redirect("aprovacoes")
    if not s.documentos.exists(): messages.error(request,"A solicitação não pode ser aprovada sem documentos anexados."); return redirect("aprovacoes")
    s.status="APROVADA"; s.data_aprovacao=timezone.now(); s.aprovado_por=request.user.get_full_name() or request.user.username; s.save(update_fields=["status","data_aprovacao","aprovado_por","atualizado_em"])
    HistoricoSolicitacao.objects.create(solicitacao=s,usuario=request.user,acao="APROVADA",detalhes="Solicitação aprovada.")
    return redirect("aprovacoes")

@login_required
def solicitar_correcao_segura(request,id):
    s=get_object_or_404(Solicitacao.objects.select_related("unidade"),pk=id)
    if not pode_aprovar_solicitacao(request.user,s): messages.error(request,"Você não possui acesso a esta solicitação."); return redirect("aprovacoes")
    if request.method=="POST":
        motivo=(request.POST.get("motivo_correcao") or request.POST.get("motivo") or "").strip()
        if not motivo: messages.error(request,"Informe o motivo da correção."); return redirect("aprovacoes")
        s.status="CORRECAO"; s.save(update_fields=["status","atualizado_em"]); HistoricoSolicitacao.objects.create(solicitacao=s,usuario=request.user,acao="CORREÇÃO",detalhes=motivo)
    return redirect("aprovacoes")

@login_required
def indeferir_seguro(request,id):
    s=get_object_or_404(Solicitacao.objects.select_related("unidade"),pk=id)
    if not pode_aprovar_solicitacao(request.user,s): messages.error(request,"Você não possui acesso a esta solicitação."); return redirect("aprovacoes")
    if request.method=="POST":
        motivo=(request.POST.get("motivo") or "").strip()
        if not motivo: messages.error(request,"Informe o motivo do indeferimento."); return redirect("aprovacoes")
        s.status="REJEITADA"; s.data_aprovacao=timezone.now(); s.save(update_fields=["status","data_aprovacao","atualizado_em"]); HistoricoSolicitacao.objects.create(solicitacao=s,usuario=request.user,acao="REJEITADA",detalhes=motivo)
    return redirect("aprovacoes")
