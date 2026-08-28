import io
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from apps.solicitacoes.models import AnexoOPO, DocumentoSolicitacao, Solicitacao, TipoDocumento
from apps.solicitacoes.pdf_security import validar_pdf_upload
from apps.solicitacoes.permissoes import eh_desenvolvedor, eh_gestor, eh_membro, pode_gerar_opo, pode_ver_solicitacao, escopo_unidades
from .operacional import gerar_opo as gerar_opo_original, gerar_mapa_eventos_pdf as mapa_pdf_original

@login_required
def documentos_solicitacao_seguro(request,id):
    s=get_object_or_404(Solicitacao.objects.select_related("unidade","municipio","bairro"),pk=id)
    if not pode_ver_solicitacao(request.user,s): messages.error(request,"Você não possui acesso aos documentos desta solicitação."); return redirect("painel_gestao")
    docs=DocumentoSolicitacao.objects.filter(solicitacao=s).select_related("tipo_documento")
    tipos=TipoDocumento.objects.filter(ativo=True).order_by("nome")
    if request.method=="POST":
        if not (eh_desenvolvedor(request.user) or eh_gestor(request.user) or eh_membro(request.user)): messages.error(request,"Você não possui permissão para anexar documentos."); return redirect("documentos_solicitacao",id=id)
        arq=request.FILES.get("arquivo"); tid=request.POST.get("tipo_documento")
        if not arq or not tid: messages.error(request,"Informe o PDF e o tipo do documento.")
        else:
            try:
                validar_pdf_upload(arq); tipo=get_object_or_404(TipoDocumento,pk=tid,ativo=True); DocumentoSolicitacao.objects.create(solicitacao=s,tipo_documento=tipo,descricao=request.POST.get("descricao","").strip(),arquivo=arq); messages.success(request,"Documento anexado com sucesso."); return redirect("documentos_solicitacao",id=id)
            except Exception as e: messages.error(request,f"Documento rejeitado: {e}")
    return render(request,"gestao/documentos_solicitacao.html",{"solicitacao":s,"documentos":docs,"tipos_documento":tipos})

@login_required
def abrir_documento_solicitacao_seguro(request,id,tipo):
    doc=get_object_or_404(DocumentoSolicitacao.objects.select_related("solicitacao__unidade"),pk=id)
    if tipo not in {"pdf","arquivo"} or not doc.arquivo: raise Http404("Arquivo não encontrado.")
    if not pode_ver_solicitacao(request.user,doc.solicitacao): messages.error(request,"Você não possui acesso a este documento."); return redirect("painel_gestao")
    return FileResponse(doc.arquivo.open("rb"),content_type="application/pdf")

@login_required
def opos_geradas_seguro(request):
    anexos=AnexoOPO.objects.select_related("solicitacao","solicitacao__unidade","solicitacao__municipio","solicitacao__bairro").filter(solicitacao__unidade__in=escopo_unidades(request.user)).order_by("-criado_em")
    grupos={}
    for a in anexos: grupos.setdefault(a.solicitacao.protocolo,{"codigo":a.solicitacao.protocolo,"solicitacao":a.solicitacao,"arquivos":[]})["arquivos"].append(a)
    return render(request,"gestao/opos_geradas.html",{"protocolos":list(grupos.values())})

@login_required
def detalhe_opo_seguro(request,id):
    s=get_object_or_404(Solicitacao.objects.select_related("municipio","bairro","unidade","tipo_evento"),pk=id)
    if not pode_ver_solicitacao(request.user,s): messages.error(request,"Você não possui acesso a esta OPO."); return redirect("painel_gestao")
    return render(request,"gestao/detalhe_opo.html",{"solicitacao":s,"anexos":AnexoOPO.objects.filter(solicitacao=s).order_by("-criado_em")})

@login_required
def gerar_opo_seguro(request,id):
    s=get_object_or_404(Solicitacao,pk=id)
    if not pode_gerar_opo(request.user,s): messages.error(request,"Você não possui permissão para gerar esta OPO."); return redirect("painel_gestao")
    return gerar_opo_original(request,id)

@login_required
def mapa_eventos_seguro(request):
    eventos=Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user),data_evento__gte=timezone.localdate()).select_related("municipio","bairro","unidade").order_by("data_evento","hora_inicio")
    return render(request,"gestao/mapa_eventos.html",{"eventos":eventos})

@login_required
def gerar_mapa_eventos_pdf_seguro(request):
    eventos=Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user),data_evento__gte=timezone.localdate()).select_related("municipio","bairro","unidade").order_by("data_evento","hora_inicio")
    return mapa_pdf_original(request) if eventos.exists() else mapa_pdf_original(request)
