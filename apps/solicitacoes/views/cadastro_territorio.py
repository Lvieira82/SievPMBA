from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

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
def editar_unidade(request, id):
    if not _dev(request):
        return _deny(request)
    unidade = get_object_or_404(Unidade, pk=id)
    if request.method == "POST":
        cpr = get_object_or_404(CPR, pk=request.POST.get("cpr"), ativo=True)
        nome = (request.POST.get("nome") or "").strip()
        sigla = (request.POST.get("sigla") or "").strip()
        tipo = (request.POST.get("tipo") or "BPM").strip()
        if not nome or not sigla:
            messages.error(request, "Nome e sigla são obrigatórios.")
        elif Unidade.objects.filter(sigla__iexact=sigla).exclude(pk=unidade.pk).exists():
            messages.error(request, "Já existe outra unidade com esta sigla.")
        else:
            unidade.cpr = cpr
            unidade.nome = nome
            unidade.sigla = sigla
            unidade.tipo = tipo
            unidade.telefone = (request.POST.get("telefone") or "").strip()
            unidade.email = (request.POST.get("email") or "").strip()
            unidade.save()
            messages.success(request, f"Unidade {sigla} atualizada com sucesso.")
            return redirect("cadastro_unidades")
    return render(request, "solicitacoes/editar_unidade.html", {
        "unidade": unidade,
        "cprs": CPR.objects.filter(ativo=True).order_by("sigla"),
        "tipos": Unidade.TIPOS,
    })


@login_required
@require_POST
def ativar_unidade(request, id):
    if not _dev(request):
        return _deny(request)
    unidade = get_object_or_404(Unidade, pk=id)
    unidade.ativo = True
    unidade.save(update_fields=["ativo"])
    messages.success(request, f"Unidade {unidade.nome} ativada.")
    return redirect("cadastro_unidades")


@login_required
@require_POST
def desativar_unidade(request, id):
    if not _dev(request):
        return _deny(request)
    unidade = get_object_or_404(Unidade, pk=id)
    unidade.ativo = False
    unidade.save(update_fields=["ativo"])
    messages.success(request, f"Unidade {unidade.nome} desativada.")
    return redirect("cadastro_unidades")


@login_required
@require_POST
def excluir_unidade(request, id):
    if not _dev(request):
        return _deny(request)
    unidade = get_object_or_404(Unidade, pk=id)
    nome = unidade.nome
    try:
        unidade.delete()
    except ProtectedError:
        messages.error(
            request,
            f"A unidade {nome} não pode ser excluída porque possui registros vinculados. "
            "Desative a unidade para preservar o histórico.",
        )
        return redirect("cadastro_unidades")

    messages.success(request, f"Unidade {nome} excluída definitivamente.")
    return redirect("cadastro_unidades")


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


@login_required
def editar_bairro(request, id):
    if not _dev(request):
        return _deny(request)
    bairro = get_object_or_404(Bairro, pk=id)
    if request.method == "POST":
        municipio = get_object_or_404(Municipio, pk=request.POST.get("municipio"), ativo=True)
        nome = (request.POST.get("nome") or "").strip()
        if not nome:
            messages.error(request, "Informe o nome do bairro ou distrito.")
        elif Bairro.objects.filter(municipio=municipio, nome__iexact=nome).exclude(pk=bairro.pk).exists():
            messages.error(request, "Este bairro já está cadastrado neste município.")
        else:
            bairro.municipio = municipio
            bairro.nome = nome
            bairro.save(update_fields=["municipio", "nome"])
            messages.success(request, f"Bairro/distrito {nome} atualizado com sucesso.")
            return redirect("cadastro_bairros")
    return render(request, "solicitacoes/editar_bairro.html", {
        "bairro": bairro,
        "municipios": Municipio.objects.filter(ativo=True).order_by("nome"),
    })


@login_required
@require_POST
def ativar_bairro(request, id):
    if not _dev(request):
        return _deny(request)
    bairro = get_object_or_404(Bairro, pk=id)
    bairro.ativo = True
    bairro.save(update_fields=["ativo"])
    messages.success(request, f"Bairro/distrito {bairro.nome} ativado.")
    return redirect("cadastro_bairros")


@login_required
@require_POST
def desativar_bairro(request, id):
    if not _dev(request):
        return _deny(request)
    bairro = get_object_or_404(Bairro, pk=id)
    bairro.ativo = False
    bairro.save(update_fields=["ativo"])
    messages.success(request, f"Bairro/distrito {bairro.nome} desativado.")
    return redirect("cadastro_bairros")


@login_required
@require_POST
def excluir_bairro(request, id):
    if not _dev(request):
        return _deny(request)
    bairro = get_object_or_404(Bairro, pk=id)
    nome = bairro.nome
    try:
        bairro.delete()
    except ProtectedError:
        messages.error(
            request,
            f"O bairro/distrito {nome} não pode ser excluído porque possui registros vinculados. "
            "Desative-o para preservar o histórico.",
        )
        return redirect("cadastro_bairros")
    messages.success(request, f"Bairro/distrito {nome} excluído definitivamente.")
    return redirect("cadastro_bairros")
