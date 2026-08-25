from django.core.exceptions import ValidationError
from django.http import JsonResponse

from .models import AreaResponsabilidade, Bairro, Municipio, Unidade


def unidades_do_municipio(municipio):
    """Retorna as unidades ativas que possuem área no município."""
    unidade_ids = (
        AreaResponsabilidade.objects
        .filter(
            bairro__municipio=municipio,
            bairro__ativo=True,
            unidade__ativo=True,
            ativo=True,
        )
        .values_list("unidade_id", flat=True)
        .distinct()
    )

    if municipio.unidade_responsavel_id:
        unidade_ids = list(unidade_ids)
        unidade_ids.append(municipio.unidade_responsavel_id)

    return (
        Unidade.objects
        .filter(id__in=set(unidade_ids), ativo=True)
        .order_by("nome")
    )


def municipio_tem_multiplas_unidades(municipio):
    return unidades_do_municipio(municipio).count() > 1


def bairros_do_municipio(municipio):
    return Bairro.objects.filter(
        municipio=municipio,
        ativo=True,
    ).order_by("nome")


def unidade_para_bairro(bairro):
    """Resolve a unidade responsável pelo bairro.

    A unidade só é escolhida automaticamente quando existe uma única
    unidade ativa para aquele bairro.
    """
    unidades = list(
        Unidade.objects.filter(
            arearesponsabilidade__bairro=bairro,
            arearesponsabilidade__ativo=True,
            ativo=True,
        ).distinct().order_by("nome")
    )

    if len(unidades) == 1:
        return unidades[0]

    if len(unidades) > 1:
        raise ValidationError(
            "O bairro selecionado possui mais de uma unidade responsável. "
            "É necessário definir a área de responsabilidade antes de enviar a solicitação."
        )

    if bairro.municipio.unidade_responsavel_id:
        return bairro.municipio.unidade_responsavel

    return None


def validar_direcionamento(municipio, bairro):
    """Valida e resolve município → bairro → unidade."""
    if bairro is None:
        if municipio_tem_multiplas_unidades(municipio):
            raise ValidationError(
                "Selecione o bairro para este município, pois existem múltiplas unidades responsáveis."
            )
        return municipio.unidade_responsavel

    if bairro.municipio_id != municipio.id:
        raise ValidationError(
            "O bairro selecionado não pertence ao município informado."
        )

    return unidade_para_bairro(bairro)


def lista_bairros(request, municipio_id):
    """API usada pelo formulário para carregar bairros do município."""
    municipio = Municipio.objects.filter(
        id=municipio_id,
        ativo=True,
    ).first()

    if not municipio:
        return JsonResponse({"erro": "Município não encontrado."}, status=404)

    unidades = unidades_do_municipio(municipio)
    bairros = bairros_do_municipio(municipio)

    dados = []
    for bairro in bairros:
        areas = list(
            AreaResponsabilidade.objects
            .filter(
                bairro=bairro,
                ativo=True,
                unidade__ativo=True,
            )
            .select_related("unidade")
            .order_by("unidade__nome")
        )

        dados.append({
            "id": bairro.id,
            "nome": bairro.nome,
            "unidades": [
                {"id": area.unidade_id, "nome": area.unidade.nome}
                for area in areas
            ],
        })

    return JsonResponse({
        "municipio": municipio.nome,
        "multiplas_unidades": unidades.count() > 1,
        "unidades": [
            {"id": unidade.id, "nome": unidade.nome}
            for unidade in unidades
        ],
        "bairros": dados,
    })
