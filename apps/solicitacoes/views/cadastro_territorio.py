from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.solicitacoes.models import Bairro, CPR, Municipio, Unidade


def _dev(request):
    return request.user.is_authenticated and request.user.is_superuser


def _deny(request):
    messages.error(request, "Somente o usuário desenvolvedor pode cadastrar unidades e bairros.")
    return redirect("painel_gestao")


@login_required
def cadastro_unidades(request):
    if not _dev(request):
        return _deny(request)
    if request.method == "POST":
        cpr = get_object_or_404(CPR, pk=request.POST.get("cpr"), ativo=True)
        nome = (request.POST.get("nome") or "").strip()
        sigla = (request.POST.get("sigla") or "").strip()
        tipo = (request.POST.get("tipo") or "BPM").strip()
        if not nome or not sigla:
            messages.error(request, "Nome e sigla são obrigatórios.")
        elif Unidade.objects.filter(sigla__iexact=sigla).exists():
            messages.error(request, "Já existe uma unidade com esta sigla.")
        else:
            Unidade.objects.create(
                cpr=cpr, nome=nome, sigla=sigla, tipo=tipo,
                telefone=(request.POST.get("telefone") or "").strip(),
                email=(request.POST.get("email") or "").strip(), ativo=True,
            )
            messages.success(request, f"Unidade {sigla} cadastrada com sucesso.")
            return redirect("cadastro_unidades")
    return render(request, "solicitacoes/cadastro_unidades.html", {
        "cprs": CPR.objects.filter(ativo=True).order_by("sigla"),
        "unidades": Unidade.objects.select_related("cpr").order_by("nome"),
        "tipos": Unidade.TIPOS,
    })


@login_required
def cadastro_bairros(request):
    if not _dev(request):
        return _deny(request)
    if request.method == "POST":
        municipio = get_object_or_404(Municipio, pk=request.POST.get("municipio"), ativo=True)
        nome = (request.POST.get("nome") or "").strip()
        if not nome:
            messages.error(request, "Informe o nome do bairro ou distrito.")
        elif Bairro.objects.filter(municipio=municipio, nome__iexact=nome).exists():
            messages.error(request, "Este bairro já está cadastrado neste município.")
        else:
            Bairro.objects.create(municipio=municipio, nome=nome, ativo=True)
            messages.success(request, f"Bairro/distrito {nome} cadastrado em {municipio.nome}.")
            return redirect("cadastro_bairros")
    return render(request, "solicitacoes/cadastro_bairros.html", {
        "municipios": Municipio.objects.filter(ativo=True).order_by("nome"),
        "bairros": Bairro.objects.select_related("municipio").order_by("municipio__nome", "nome"),
    })
