from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from apps.solicitacoes.models import AnexoOPO, CumprimentoOPO, LogSistema, Solicitacao
from apps.solicitacoes.permissoes import eh_operador, pode_ver_solicitacao
_EXTENSOES_IMAGEM={"jpg","jpeg","png","webp"}; _MAX_IMAGEM=5*1024*1024; _MAX_JUSTIFICATIVA=150

def _operador_autorizado(request,solicitacao):
    acesso=getattr(request.user,"acesso_institucional",None)
    return bool(eh_operador(request.user) and acesso and acesso.unidade_id and solicitacao.unidade_id==acesso.unidade_id and solicitacao.status=="APROVADA" and solicitacao.data_evento==timezone.localdate())
def _opo_principal(solicitacao): return AnexoOPO.objects.filter(solicitacao=solicitacao).exclude(arquivo="").order_by("-criado_em").first()
def _pasta_protocolo(protocolo): return Path("protocolos")/protocolo

def _comprimir_imagem_80_porcento(imagem):
    original_size=max(int(getattr(imagem,"size",0) or 0),1); imagem.seek(0); origem=ImageOps.exif_transpose(Image.open(imagem))
    if origem.mode in ("RGBA","LA","P"):
        fundo=Image.new("RGB",origem.size,"white")
        if origem.mode!="RGBA": origem=origem.convert("RGBA")
        fundo.paste(origem,mask=origem.getchannel("A")); origem=fundo
    else: origem=origem.convert("RGB")
    qualidade=75; atual=origem; melhor=None
    while True:
        saida=BytesIO(); atual.save(saida,format="JPEG",quality=qualidade,optimize=True,progressive=True); dados=saida.getvalue(); melhor=dados
        if len(dados)<=original_size*.20 or qualidade<=20: break
        if qualidade>35: qualidade-=10
        else:
            largura,altura=atual.size; nova_largura=max(640,int(largura*.85)); nova_altura=max(640,int(altura*.85))
            if (nova_largura,nova_altura)==(largura,altura): qualidade-=5
            else: atual=atual.resize((nova_largura,nova_altura),Image.Resampling.LANCZOS)
    return melhor

def _salvar_comprovacao_no_protocolo(solicitacao,imagem):
    nome=f"comprovacao_opo_{timezone.localtime():%Y%m%d_%H%M%S_%f}.jpg"; caminho=str(_pasta_protocolo(solicitacao.protocolo or "SEM_PROTOCOLO")/nome)
    return default_storage.save(caminho,ContentFile(_comprimir_imagem_80_porcento(imagem)))
def _nome_justificativa(operador,respondido_em):
    identificador=getattr(operador,"username","operador") or "operador"; seguro="".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in identificador)
    return f"justificativa_opo_{seguro}_{timezone.localtime(respondido_em):%Y%m%d_%H%M%S_%f}.txt"
def _salvar_justificativa_txt_no_protocolo(solicitacao,operador,justificativa,respondido_em):
    protocolo=solicitacao.protocolo or "SEM_PROTOCOLO"; caminho=str(_pasta_protocolo(protocolo)/_nome_justificativa(operador,respondido_em))
    conteudo=f"PROTOCOLO: {protocolo}\nOPERADOR: {getattr(operador,'username','operador') or 'operador'}\nDATA/HORA: {timezone.localtime(respondido_em):%d/%m/%Y %H:%M:%S}\n\nJUSTIFICATIVA:\n{justificativa}\n"
    return default_storage.save(caminho,ContentFile(conteudo.encode("utf-8")))

@login_required
@require_http_methods(["GET","POST"])
def cumprimento_opo(request,solicitacao_id):
    if request.method=="GET" and request.GET.get("imagem_id"):
        cumprimento=get_object_or_404(CumprimentoOPO.objects.select_related("opo","opo__solicitacao"),pk=request.GET.get("imagem_id")); solicitacao= cumprimento.opo.solicitacao
        if eh_operador(request.user) or not pode_ver_solicitacao(request.user,solicitacao):
            messages.error(request,"Você não possui acesso à foto deste cumprimento."); return redirect("painel_gestao")
        if not cumprimento.imagem: raise Http404("A foto do cumprimento não está disponível.")
        nome=getattr(cumprimento.imagem,"name","") or ""
        if not nome: raise Http404("A foto do cumprimento não possui nome de arquivo.")
        try:
            if default_storage.exists(nome): arquivo=default_storage.open(nome,"rb")
            else:
                caminho=Path(settings.MEDIA_ROOT)/nome
                if not caminho.is_file(): raise Http404("A foto do cumprimento não foi encontrada no armazenamento.")
                arquivo=caminho.open("rb")
        except (OSError,ValueError): raise Http404("A foto do cumprimento não foi encontrada no armazenamento.")
        resposta=FileResponse(arquivo,content_type="image/jpeg"); resposta["Content-Disposition"]=f'inline; filename="{Path(nome).name}"'; resposta["X-Content-Type-Options"]="nosniff"; return resposta
    solicitacao=get_object_or_404(Solicitacao.objects.select_related("municipio","bairro","unidade"),pk=solicitacao_id)
    if not _operador_autorizado(request,solicitacao): messages.error(request,"Esta OPO não está liberada para o seu acesso de operador."); return redirect("eventos_dia")
    opo=_opo_principal(solicitacao)
    if not opo: messages.error(request,"A OPO deste evento ainda não possui arquivo disponível."); return redirect("eventos_dia")
    registro,_=CumprimentoOPO.objects.get_or_create(opo=opo,operador=request.user)
    if request.method=="POST":
        resposta=request.POST.get("cumprida"); imagem=request.FILES.get("imagem"); justificativa=(request.POST.get("justificativa") or "").strip(); latitude=(request.POST.get("latitude") or "").strip(); longitude=(request.POST.get("longitude") or "").strip()
        if resposta not in {"SIM","NAO"}: messages.error(request,"Informe se a OPO foi cumprida.")
        elif resposta=="SIM":
            if not imagem: messages.error(request,"A foto do cumprimento deve ser capturada pela câmera do dispositivo.")
            else:
                extensao=Path(imagem.name).suffix.lower().lstrip(".")
                if extensao not in _EXTENSOES_IMAGEM: messages.error(request,"A imagem deve estar em JPG, JPEG, PNG ou WEBP.")
                elif imagem.size>_MAX_IMAGEM: messages.error(request,"A imagem deve ter no máximo 5 MB.")
                elif not latitude or not longitude: messages.error(request,"Não foi possível obter a localização GPS. Autorize a localização do dispositivo e tente novamente.")
                else:
                    try:
                        latitude_float=float(latitude); longitude_float=float(longitude)
                        if not (-90<=latitude_float<=90 and -180<=longitude_float<=180): raise ValueError
                    except (TypeError,ValueError): messages.error(request,"As coordenadas GPS recebidas são inválidas.")
                    else:
                        try: caminho_imagem=_salvar_comprovacao_no_protocolo(solicitacao,imagem)
                        except Exception: messages.error(request,"Não foi possível processar a foto capturada. Tente novamente.")
                        else:
                            if registro.imagem:
                                try: registro.imagem.delete(save=False)
                                except Exception: pass
                            registro.cumprida=True; registro.imagem.name=caminho_imagem; registro.justificativa=""; registro.respondido_em=timezone.now(); registro.save()
                            LogSistema.objects.create(usuario=request.user,solicitacao=solicitacao,acao="CUMPRIMENTO OPO",detalhes=f"OPO cumprida. Coordenadas GPS: latitude={latitude_float:.7f}, longitude={longitude_float:.7f}.")
                            messages.success(request,"Cumprimento registrado como SIM, com foto e localização GPS.")
                            return redirect("eventos_dia")
        else:
            if not justificativa: messages.error(request,"Informe a justificativa quando a OPO não for cumprida.")
            elif len(justificativa)>_MAX_JUSTIFICATIVA: messages.error(request,"A justificativa deve ter no máximo 150 caracteres.")
            else:
                respondido_em=timezone.now()
                try: caminho_justificativa=_salvar_justificativa_txt_no_protocolo(solicitacao,request.user,justificativa,respondido_em)
                except Exception: messages.error(request,"Não foi possível salvar a justificativa. Tente novamente.")
                else:
                    if registro.imagem:
                        try: registro.imagem.delete(save=False)
                        except Exception: pass
                    registro.cumprida=False; registro.imagem=None; registro.justificativa=justificativa; registro.respondido_em=respondido_em; registro.save()
                    LogSistema.objects.create(usuario=request.user,solicitacao=solicitacao,acao="CUMPRIMENTO OPO",detalhes=f"OPO não cumprida. Justificativa salva em: {caminho_justificativa}.")
                    messages.success(request,"Registro de não cumprimento salvo com justificativa.")
                    return redirect("eventos_dia")
    return render(request,"solicitacoes/cumprimento_opo.html",{"solicitacao":solicitacao,"opo":opo,"registro":registro})

@login_required
def abrir_opo_operador(request,anexo_id):
    opo=get_object_or_404(AnexoOPO.objects.select_related("solicitacao","solicitacao__unidade"),pk=anexo_id)
    if not _operador_autorizado(request,opo.solicitacao): messages.error(request,"Esta OPO não está liberada para o seu acesso de operador."); return redirect("eventos_dia")
    if not opo.arquivo: messages.error(request,"O arquivo da OPO não está disponível."); return redirect("cumprimento_opo",solicitacao_id=opo.solicitacao_id)
    nome=getattr(opo.arquivo,"name","") or ""
    if not nome: raise Http404("O arquivo da OPO não possui nome.")
    try:
        if default_storage.exists(nome): arquivo=default_storage.open(nome,"rb")
        else:
            caminho=Path(settings.MEDIA_ROOT)/nome
            if not caminho.is_file(): raise Http404("O arquivo da OPO não foi encontrado no armazenamento.")
            arquivo=caminho.open("rb")
    except (OSError,ValueError): raise Http404("O arquivo da OPO não foi encontrado no armazenamento.")
    resposta=FileResponse(arquivo,content_type="application/pdf"); resposta["Content-Disposition"]=f'inline; filename="{Path(nome).name}"'; resposta["X-Content-Type-Options"]="nosniff"; return resposta
