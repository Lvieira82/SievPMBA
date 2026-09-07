import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.solicitacoes.models import AreaResponsabilidade, Bairro, Municipio, Unidade


def _desenvolvedor(request):
    return request.user.is_authenticated and request.user.is_superuser


def _negar(request):
    messages.error(request, "Somente o usuário desenvolvedor pode administrar o território.")
    return redirect("painel_gestao")


@login_required
@require_http_methods(["GET", "POST"])
def areas_responsabilidade(request):
    if not _desenvolvedor(request):
        return _negar(request)
    if request.method == "POST":
        municipio_id = request.POST.get("municipio")
        bairro_nome = (request.POST.get("bairro") or "").strip()
        unidade_id = request.POST.get("unidade")
        municipio = get_object_or_404(Municipio, pk=municipio_id, ativo=True)
        unidade = get_object_or_404(Unidade, pk=unidade_id, ativo=True)
        if not bairro_nome:
            messages.error(request, "Informe o bairro ou distrito.")
        else:
            bairro, _ = Bairro.objects.get_or_create(municipio=municipio, nome=bairro_nome)
            AreaResponsabilidade.objects.update_or_create(bairro=bairro, defaults={"unidade": unidade, "ativo": True})
            messages.success(request, f"{municipio.nome} / {bairro.nome} → {unidade.nome} salvo com sucesso.")
            return redirect("areas_responsabilidade")
    areas = AreaResponsabilidade.objects.select_related("bairro", "bairro__municipio", "unidade").order_by("bairro__municipio__nome", "bairro__nome")
    return render(request, "solicitacoes/areas_responsabilidade.html", {
        "areas": areas,
        "municipios": Municipio.objects.filter(ativo=True).order_by("nome"),
        "unidades": Unidade.objects.filter(ativo=True).order_by("nome"),
    })


@login_required
def editar_area_responsabilidade(request, id):
    if not _desenvolvedor(request):
        return _negar(request)
    area = get_object_or_404(AreaResponsabilidade, pk=id)
    if request.method == "POST":
        municipio = get_object_or_404(Municipio, pk=request.POST.get("municipio"), ativo=True)
        bairro = get_object_or_404(Bairro, pk=request.POST.get("bairro"), municipio=municipio, ativo=True)
        unidade = get_object_or_404(Unidade, pk=request.POST.get("unidade"), ativo=True)
        if AreaResponsabilidade.objects.filter(bairro=bairro).exclude(pk=area.pk).exists():
            messages.error(request, "Este bairro já possui outra unidade responsável.")
        else:
            area.bairro = bairro
            area.unidade = unidade
            area.ativo = True
            area.save()
            messages.success(request, "Área de responsabilidade atualizada.")
            return redirect("areas_responsabilidade")
    return render(request, "solicitacoes/editar_area_responsabilidade.html", {
        "area": area,
        "municipios": Municipio.objects.filter(ativo=True).order_by("nome"),
        "bairros": Bairro.objects.filter(municipio=area.bairro.municipio, ativo=True).order_by("nome"),
        "unidades": Unidade.objects.filter(ativo=True).order_by("nome"),
    })


@login_required
@require_http_methods(["POST"])
def ativar_area_responsabilidade(request, id):
    if not _desenvolvedor(request):
        return _negar(request)
    area = get_object_or_404(AreaResponsabilidade, pk=id)
    area.ativo = True
    area.save(update_fields=["ativo"])
    messages.success(request, "Área de responsabilidade ativada.")
    return redirect("areas_responsabilidade")


@login_required
@require_http_methods(["POST"])
def desativar_area_responsabilidade(request, id):
    if not _desenvolvedor(request):
        return _negar(request)
    area = get_object_or_404(AreaResponsabilidade, pk=id)
    area.ativo = False
    area.save(update_fields=["ativo"])
    messages.success(request, "Área de responsabilidade desativada.")
    return redirect("areas_responsabilidade")


@login_required
@require_http_methods(["POST"])
def excluir_area_responsabilidade(request, id):
    if not _desenvolvedor(request):
        return _negar(request)
    area = get_object_or_404(AreaResponsabilidade, pk=id)
    try:
        area.delete()
    except ProtectedError:
        messages.error(request, "Esta área não pode ser excluída por possuir registros vinculados.")
    else:
        messages.success(request, "Área de responsabilidade excluída.")
    return redirect("areas_responsabilidade")


@login_required
@require_http_methods(["POST"])
def importar_areas_responsabilidade(request):
    if not _desenvolvedor(request):
        return _negar(request)
    arquivo = request.FILES.get("arquivo")
    if not arquivo:
        messages.error(request, "Selecione um arquivo CSV.")
        return redirect("areas_responsabilidade")
    if arquivo.size > 5 * 1024 * 1024:
        messages.error(request, "O CSV deve ter no máximo 5 MB.")
        return redirect("areas_responsabilidade")
    try:
        texto = arquivo.read().decode("utf-8-sig")
        leitor = csv.DictReader(io.StringIO(texto))
        campos = {str(c).strip().lower() for c in (leitor.fieldnames or [])}
        obrigatorios = {"municipio", "bairro", "unidade"}
        if not obrigatorios.issubset(campos):
            raise ValueError("O CSV precisa conter municipio,bairro,unidade.")
        total = 0
        for numero, linha in enumerate(leitor, start=2):
            dados = {str(k).strip().lower(): (v or "").strip() for k, v in linha.items()}
            municipio = Municipio.objects.filter(nome__iexact=dados.get("municipio", ""), ativo=True).first()
            unidade = Unidade.objects.filter(nome__iexact=dados.get("unidade", ""), ativo=True).first() or Unidade.objects.filter(sigla__iexact=dados.get("unidade", ""), ativo=True).first()
            bairro_nome = dados.get("bairro", "")
            if not municipio or not unidade or not bairro_nome:
                raise ValueError(f"Linha {numero}: município, bairro ou unidade inválidos.")
            bairro, _ = Bairro.objects.get_or_create(municipio=municipio, nome=bairro_nome)
            AreaResponsabilidade.objects.update_or_create(bairro=bairro, defaults={"unidade": unidade, "ativo": True})
            total += 1
        messages.success(request, f"{total} áreas importadas/atualizadas.")
    except (UnicodeDecodeError, ValueError) as exc:
        messages.error(request, f"Importação não realizada: {exc}")
    return redirect("areas_responsabilidade")


@login_required
@require_http_methods(["GET"])
def bairros_por_municipio(request, municipio_id):
    municipio = get_object_or_404(Municipio, pk=municipio_id, ativo=True)
    bairros = Bairro.objects.filter(municipio=municipio, ativo=True).order_by("nome")
    unidades_ids = AreaResponsabilidade.objects.filter(bairro__municipio=municipio, ativo=True).values_list("unidade_id", flat=True).distinct()
    return JsonResponse({"multiplas_unidades": len(set(unidades_ids)) > 1, "bairros": [{"id": b.id, "nome": b.nome} for b in bairros]})
