from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.solicitacoes.models import Municipio


def _dev(request):
    return request.user.is_authenticated and request.user.is_superuser


def _deny(request):
    messages.error(request, "Somente o Desenvolvedor pode administrar cidades/municípios.")
    return redirect("painel_gestao")


@login_required
def cadastro_municipios(request):
    if not _dev(request):
        return _deny(request)
    if request.method == "POST":
        nome = (request.POST.get("nome") or "").strip()
        ibge = (request.POST.get("ibge") or "").strip()
        if not nome:
            messages.error(request, "Informe o nome da cidade/município.")
        elif Municipio.objects.filter(nome__iexact=nome).exists():
            messages.error(request, "Esta cidade/município já está cadastrado.")
        else:
            Municipio.objects.create(nome=nome, ibge=ibge or None, ativo=True)
            messages.success(request, f"Cidade/município {nome} cadastrado com sucesso.")
            return redirect("cadastro_municipios")
    municipios = Municipio.objects.select_related("unidade_responsavel").order_by("nome")
    return render(request, "solicitacoes/cadastro_municipios.html", {"municipios": municipios})


@login_required
@require_POST
def alternar_municipio(request, id):
    if not _dev(request):
        return _deny(request)
    municipio = get_object_or_404(Municipio, pk=id)
    municipio.ativo = not municipio.ativo
    municipio.save(update_fields=["ativo"])
    messages.success(request, f"Município {municipio.nome}: {'ativo' if municipio.ativo else 'inativo'}.")
    return redirect("cadastro_municipios")
