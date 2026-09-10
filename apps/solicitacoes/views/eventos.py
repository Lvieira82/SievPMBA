from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import AnexoOPO, CumprimentoOPO, LogSistema, Solicitacao
from ..models_acesso import AcessoInstitucional

MOTIVOS_NAO={"VIATURA_PROBLEMA":"Viatura apresentou problema","DELEGACIA":"Apresentação na delegacia","OCORRENCIA":"Guarnição em Ocorrência","ENDERECO":"Endereço não encontrado","CANCELADO":"Evento Cancelado","HORARIO":"Horário alterado"}

def _acesso_por_matricula(matricula):
    return AcessoInstitucional.objects.select_related("usuario","cpr","unidade").filter(matricula__iexact=matricula,ativo=True,usuario__is_active=True).first()

def _eventos_do_acesso(acesso,hoje):
    eventos=Solicitacao.objects.filter(data_evento=hoje,status="APROVADA").select_related("municipio","unidade","bairro").order_by("hora_inicio","nome_evento")
    if acesso.perfil=="OPERADOR":
        if not acesso.unidade_id:return eventos.none()
        return eventos.filter(unidade_id=acesso.unidade_id)
    if acesso.perfil=="UNIDADE":return eventos.filter(unidade_id=acesso.unidade_id)
    if acesso.perfil=="CPR":return eventos.filter(unidade__cpr_id=acesso.cpr_id)
    if acesso.perfil=="COPPM":return eventos
    return eventos.none()

def _eventos_offline_payload(eventos):
    return [{"id":e.id,"opo":e.protocolo or str(e.id),"endereco":e.local or "","telefone":e.telefone or "","solicitante":e.solicitante or ""} for e in eventos]

def _eventos_registrados(eventos, usuario):
    ids=[e.id for e in eventos]
    if not ids:return set()
    return set(CumprimentoOPO.objects.filter(opo__solicitacao_id__in=ids,operador=usuario,respondido_em__isnull=False).values_list("opo__solicitacao_id",flat=True))

def _service_worker_script():
    return '''const CACHE="sievpm-eventos-v5";const OFFLINE="/static/pwa/eventos_offline.html";const JS="/static/pwa/eventos_offline.js?v=3";self.addEventListener("install",event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll([OFFLINE,JS])).then(()=>self.skipWaiting())));self.addEventListener("activate",event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith("sievpm-eventos-")&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));self.addEventListener("fetch",event=>{const u=new URL(event.request.url);if(u.pathname==="/static/pwa/eventos_offline.html"||u.pathname==="/static/pwa/eventos_offline.js"){event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request)));return}if(event.request.mode!=="navigate"||u.pathname!=="/eventos-do-dia/resultado/")return;event.respondWith(fetch(event.request).catch(()=>caches.match(OFFLINE)));});'''

@login_required
def eventos_dia(request):
    if request.GET.get("sw")=="1":return HttpResponse(_service_worker_script(),content_type="application/javascript")
    if request.method=="POST" and request.headers.get("X-Offline-Sync")=="1":return sincronizar_evento_offline(request)
    acesso_logado=getattr(request.user,"acesso_institucional",None)
    if not acesso_logado or not acesso_logado.ativo or not request.user.is_active:
        messages.error(request,"Acesso institucional não autorizado.");return redirect("login_gestao")
    if request.method=="GET":return render(request,"solicitacoes/eventos_dia.html",{"acesso_logado":acesso_logado})
    matricula=request.POST.get("matricula","").strip() or acesso_logado.matricula;acesso=_acesso_por_matricula(matricula)
    if not acesso:return render(request,"solicitacoes/eventos_dia.html",{"erro":"Matrícula sem acesso institucional ativo.","acesso_logado":acesso_logado})
    if acesso.usuario_id!=request.user.id:return render(request,"solicitacoes/eventos_dia.html",{"erro":"A matrícula informada não corresponde ao usuário autenticado.","acesso_logado":acesso_logado})
    hoje=timezone.localdate();eventos=_eventos_do_acesso(acesso,hoje);request.session["eventos_acesso_id"]=acesso.id;request.session["eventos_matricula"]=acesso.matricula;request.session["eventos_opos_autorizadas"]=list(eventos.values_list("id",flat=True));return render(request,"solicitacoes/eventos_dia_resultado.html",{"eventos":eventos,"matricula":acesso.matricula,"acesso":acesso,"unidade":acesso.unidade,"data":hoje,"data_eventos":hoje,"offline_eventos":_eventos_offline_payload(eventos),"eventos_registrados":_eventos_registrados(eventos,request.user)})

@login_required
def eventos_dia_resultado(request):
    acesso_id=request.session.get("eventos_acesso_id")
    if not acesso_id:return redirect("eventos_dia")
    acesso=AcessoInstitucional.objects.select_related("usuario","cpr","unidade").filter(id=acesso_id,ativo=True,usuario__is_active=True).first()
    if not acesso or acesso.usuario_id!=request.user.id:
        for chave in ("eventos_acesso_id","eventos_matricula","eventos_opos_autorizadas"):request.session.pop(chave,None)
        messages.error(request,"Acesso não autorizado.");return redirect("login_gestao")
    hoje=timezone.localdate();eventos=_eventos_do_acesso(acesso,hoje);request.session["eventos_opos_autorizadas"]=list(eventos.values_list("id",flat=True));return render(request,"solicitacoes/eventos_dia_resultado.html",{"eventos":eventos,"perfil":acesso,"acesso":acesso,"matricula":acesso.matricula,"unidade":acesso.unidade,"data":hoje,"data_eventos":hoje,"offline_eventos":_eventos_offline_payload(eventos),"eventos_registrados":_eventos_registrados(eventos,request.user)})

@login_required
@require_POST
def sincronizar_evento_offline(request):
    acesso=getattr(request.user,"acesso_institucional",None)
    if not acesso or not acesso.ativo or not request.user.is_active or acesso.perfil!="OPERADOR" or not acesso.unidade_id:return JsonResponse({"ok":False,"erro":"Acesso de operador inválido."},status=403)
    try:evento_id=int(request.POST.get("evento_id"))
    except (TypeError,ValueError):return JsonResponse({"ok":False,"erro":"Evento inválido."},status=400)
    solicitacao=Solicitacao.objects.select_related("unidade","municipio","bairro").filter(id=evento_id,data_evento=timezone.localdate(),status="APROVADA",unidade_id=acesso.unidade_id).first()
    if not solicitacao:return JsonResponse({"ok":False,"erro":"Evento não autorizado para este operador."},status=403)
    opo=AnexoOPO.objects.filter(solicitacao=solicitacao).exclude(arquivo="").order_by("-criado_em").first()
    if not opo:return JsonResponse({"ok":False,"erro":"OPO não encontrada."},status=404)
    resposta=request.POST.get("cumprida")
    if resposta not in {"SIM","NAO"}:return JsonResponse({"ok":False,"erro":"Resposta inválida."},status=400)
    registro,_=CumprimentoOPO.objects.get_or_create(opo=opo,operador=request.user)
    if registro.respondido_em is not None:
        return JsonResponse({"ok":True,"ja_registrado":True})
    latitude=(request.POST.get("latitude") or "").strip();longitude=(request.POST.get("longitude") or "").strip();precisao=(request.POST.get("precisao") or "").strip()
    if resposta=="SIM":
        imagem=request.FILES.get("imagem")
        if not imagem or not latitude or not longitude:return JsonResponse({"ok":False,"erro":"Foto e GPS são obrigatórios."},status=400)
        try:
            lat=float(latitude);lon=float(longitude)
            if not(-90<=lat<=90 and -180<=lon<=180):raise ValueError
        except (TypeError,ValueError):return JsonResponse({"ok":False,"erro":"Coordenadas GPS inválidas."},status=400)
        try:
            from .cumprimento_opo import _organizar_documentacao_opo, _salvar_comprovacao_no_protocolo
            caminho=_salvar_comprovacao_no_protocolo(solicitacao,imagem)
        except Exception:return JsonResponse({"ok":False,"erro":"Não foi possível salvar a foto."},status=500)
        if registro.imagem:
            try:registro.imagem.delete(save=False)
            except Exception:pass
        registro.cumprida=True;registro.imagem.name=caminho;registro.justificativa="";registro.respondido_em=timezone.now();registro.save()
        try:_organizar_documentacao_opo(solicitacao,opo=opo,caminho_imagem=caminho,latitude=f"{lat:.7f}",longitude=f"{lon:.7f}",precisao=precisao,operador=request.user)
        except Exception:pass
        LogSistema.objects.create(usuario=request.user,solicitacao=solicitacao,acao="CUMPRIMENTO OPO OFFLINE",detalhes=f"Registro sincronizado. Coordenadas GPS: latitude={lat:.7f}, longitude={lon:.7f}, precisão={precisao or 'não informada'}.")
    else:
        justificativa=(request.POST.get("justificativa") or "").strip();motivos=[m for m in request.POST.getlist("motivos_nao") if m in MOTIVOS_NAO]
        if not motivos:return JsonResponse({"ok":False,"erro":"Selecione pelo menos um motivo para o não cumprimento."},status=400)
        if len(justificativa)>150:return JsonResponse({"ok":False,"erro":"As observações devem ter no máximo 150 caracteres."},status=400)
        if registro.imagem:
            try:registro.imagem.delete(save=False)
            except Exception:pass
        registro.cumprida=False;registro.imagem=None;registro.justificativa=justificativa;registro.respondido_em=timezone.now();registro.save()
        try:
            from .cumprimento_opo import _organizar_documentacao_opo, _salvar_justificativa_txt_no_protocolo
            caminho_justificativa=_salvar_justificativa_txt_no_protocolo(solicitacao,request.user,justificativa,registro.respondido_em)
            _organizar_documentacao_opo(solicitacao,opo=opo,caminho_justificativa=caminho_justificativa,operador=request.user)
        except Exception:
            caminho_justificativa=""
        nomes=[MOTIVOS_NAO[m] for m in motivos];detalhes=f"Registro sincronizado como não cumprida. Motivos: {'; '.join(nomes)}."
        if justificativa:detalhes+=f" Observações: {justificativa}"
        LogSistema.objects.create(usuario=request.user,solicitacao=solicitacao,acao="CUMPRIMENTO OPO OFFLINE",detalhes=detalhes)
    return JsonResponse({"ok":True})
