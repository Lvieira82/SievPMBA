import unicodedata

from django.core.exceptions import ValidationError
from django.http import JsonResponse

from .models import AreaResponsabilidade, Bairro, Municipio, Unidade


def _normalizar(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _areas_do_bairro(bairro):
    return list(
        AreaResponsabilidade.objects
        .filter(
            bairro=bairro,
            ativo=True,
            unidade__ativo=True,
        )
        .select_related("unidade", "bairro__municipio")
        .order_by("id")
    )


def _area_correta_do_bairro(bairro):
    """Retorna uma única área para o bairro.

    Regra territorial do SiEv: um bairro/distrito pertence a uma única
    unidade. Se houver registros antigos duplicados, primeiro tenta preservar
    a unidade cujo nome identifica o próprio município do bairro. Isso evita
    que um bairro com o mesmo nome em cidades diferentes herde a unidade de
    outro município.
    """
    areas = _areas_do_bairro(bairro)

    if not areas:
        return None

    if len(areas) == 1:
        return areas[0]

    municipio = _normalizar(bairro.municipio.nome)
    correspondentes = []

    for area in areas:
        unidade_texto = _normalizar(area.unidade.nome)
        if municipio and municipio in unidade_texto:
            correspondentes.append(area)

    if len(correspondentes) == 1:
        return correspondentes[0]

    # Compatibilidade com cadastros antigos que ainda possuam duplicidade.
    # Mantém a associação mais recente até que o cadastro territorial seja
    # corrigido pelo desenvolvedor.
    return areas[-1]


def unidades_do_municipio(municipio):
    """Retorna as unidades ativas que possuem área no município."""
    unidade_ids = []
    bairros = bairros_do_municipio(municipio)

    for bairro in bairros:
        area = _area_correta_do_bairro(bairro)
        if area:
            unidade_ids.append(area.unidade_id)

    if municipio.unidade_responsavel_id:
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
    """Resolve a única unidade responsável pelo bairro."""
    area = _area_correta_do_bairro(bairro)
    if area:
        return area.unidade

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
        area = _area_correta_do_bairro(bairro)

        dados.append({
            "id": bairro.id,
            "nome": bairro.nome,
            "unidades": ([
                {
                    "id": area.unidade_id,
                    "nome": area.unidade.nome,
                }
            ] if area else []),
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
