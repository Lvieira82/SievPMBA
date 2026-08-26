from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Prefetch

from apps.solicitacoes.models import (
    AreaResponsabilidade,
    Bairro,
    CPR,
    Municipio,
    Unidade,
)


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
        municipio = get_object_or_404(
            Municipio,
            pk=request.POST.get("municipio"),
            ativo=True,
        )
        unidade = get_object_or_404(
            Unidade.objects.select_related("cpr"),
            pk=request.POST.get("unidade"),
            ativo=True,
            cpr__ativo=True,
        )
        nome = (request.POST.get("nome") or "").strip()

        if not nome:
            messages.error(request, "Informe o nome do bairro ou distrito.")
        else:
            with transaction.atomic():
                bairro = Bairro.objects.filter(
                    municipio=municipio,
                    nome__iexact=nome,
                ).first()

                if bairro:
                    area = AreaResponsabilidade.objects.filter(
                        bairro=bairro,
                        ativo=True,
                    ).first()

                    if area:
                        messages.error(
                            request,
                            f"O bairro/distrito {bairro.nome} já está vinculado à unidade {area.unidade.sigla}.",
                        )
                    else:
                        AreaResponsabilidade.objects.update_or_create(
                            bairro=bairro,
                            unidade=unidade,
                            defaults={"ativo": True},
                        )
                        messages.success(
                            request,
                            f"Bairro/distrito {bairro.nome} vinculado à unidade {unidade.sigla}.",
                        )
                        return redirect("cadastro_bairros")
                else:
                    bairro = Bairro.objects.create(
                        municipio=municipio,
                        nome=nome,
                        ativo=True,
                    )
                    AreaResponsabilidade.objects.create(
                        bairro=bairro,
                        unidade=unidade,
                        ativo=True,
                    )
                    messages.success(
                        request,
                        f"Bairro/distrito {nome} cadastrado em {municipio.nome} e vinculado à unidade {unidade.sigla}.",
                    )
                    return redirect("cadastro_bairros")

    areas_prefetch = Prefetch(
        "arearesponsabilidade_set",
        queryset=AreaResponsabilidade.objects.select_related("unidade", "unidade__cpr").filter(ativo=True),
        to_attr="areas_responsabilidade",
    )

    return render(request, "solicitacoes/cadastro_bairros.html", {
        "municipios": Municipio.objects.filter(ativo=True).order_by("nome"),
        "unidades": Unidade.objects.select_related("cpr").filter(
            ativo=True,
            cpr__ativo=True,
        ).order_by("cpr__sigla", "sigla", "nome"),
        "bairros": Bairro.objects.select_related("municipio").prefetch_related(
            areas_prefetch
        ).order_by("municipio__nome", "nome"),
    })
