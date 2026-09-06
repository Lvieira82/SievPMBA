import importlib
import unicodedata

from django.db import migrations


MIGRACAO_TERRITORIAL = (
    "apps.solicitacoes.migrations.0012_aplicar_areas_responsabilidade_csv"
)
MIGRACAO_FEIRA = (
    "apps.solicitacoes.migrations.0013_cadastrar_unidades_bairros_feira_santana"
)


def normalizar(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar_unidade(texto):
    texto = normalizar(texto)
    texto = texto.split("/", 1)[0]
    return texto.replace("º", "").replace("ª", "").strip()


def carregar_mapeamento_autoritativo():
    """Carrega a fonte territorial já versionada no próprio projeto.

    A chave sempre contém MUNICÍPIO + BAIRRO. Portanto, homônimos em cidades
    diferentes jamais são misturados.

    Quando a fonte histórica possui a mesma chave mais de uma vez, a última
    ocorrência é tratada como a correção mais recente da própria fonte.
    """
    fonte = importlib.import_module(MIGRACAO_TERRITORIAL)
    mapeamento = {}

    for municipio, bairro, unidade in fonte.DADOS_TERRITORIAIS:
        mapeamento[(normalizar(municipio), normalizar(bairro))] = normalizar_unidade(unidade)

    # A migration 0013 é posterior e contém a nomenclatura mais específica
    # das unidades de Feira de Santana. Ela prevalece para os registros dela.
    feira = importlib.import_module(MIGRACAO_FEIRA)
    for nome_unidade, bairros in feira.BAIRROS.items():
        for bairro in bairros:
            mapeamento[(normalizar("Feira de Santana"), normalizar(bairro))] = normalizar_unidade(nome_unidade)

    return mapeamento


def localizar_municipio(Municipio, nome):
    candidatos = [
        municipio
        for municipio in Municipio.objects.all()
        if normalizar(municipio.nome) == normalizar(nome)
    ]

    if len(candidatos) > 1:
        raise RuntimeError(
            f"Território inconsistente: existem municípios duplicados para '{nome}'."
        )

    return candidatos[0] if candidatos else None


def localizar_bairro(Bairro, municipio, nome):
    exatos = list(
        Bairro.objects.filter(municipio=municipio, nome__iexact=nome).order_by("id")
    )
    if len(exatos) == 1:
        return exatos[0]
    if len(exatos) > 1:
        raise RuntimeError(
            f"Território inconsistente: município '{municipio.nome}' possui bairros duplicados com o nome '{nome}'."
        )

    normalizados = [
        bairro
        for bairro in Bairro.objects.filter(municipio=municipio).order_by("id")
        if normalizar(bairro.nome) == normalizar(nome)
    ]

    if len(normalizados) > 1:
        raise RuntimeError(
            f"Território inconsistente: município '{municipio.nome}' possui mais de um bairro equivalente a '{nome}'."
        )

    return normalizados[0] if normalizados else None


def localizar_unidade(Unidade, chave):
    candidatos = []
    for unidade in Unidade.objects.filter(ativo=True).order_by("id"):
        chaves = {
            normalizar_unidade(unidade.nome),
            normalizar_unidade(unidade.sigla),
        }
        if chave in chaves:
            candidatos.append(unidade)

    if len(candidatos) != 1:
        nomes = ", ".join(
            f"{u.id}:{u.nome}" for u in candidatos
        ) or "nenhuma unidade ativa"
        raise RuntimeError(
            f"Território inconsistente: a unidade '{chave}' não pôde ser resolvida de forma única ({nomes})."
        )

    return candidatos[0]


def ajustar_bairro(AreaResponsabilidade, bairro, unidade):
    """Deixa exatamente uma área para o bairro, preservando o registro escolhido."""
    areas = list(
        AreaResponsabilidade.objects.filter(bairro=bairro).order_by("id")
    )

    alvo = next(
        (area for area in areas if area.unidade_id == unidade.id),
        None,
    )

    if alvo is None and areas:
        alvo = areas[0]
        alvo.unidade_id = unidade.id

    if alvo is None:
        alvo = AreaResponsabilidade.objects.create(
            bairro=bairro,
            unidade=unidade,
            ativo=True,
        )
    else:
        alvo.ativo = True
        alvo.unidade_id = unidade.id
        alvo.save(update_fields=["unidade", "ativo"])

    AreaResponsabilidade.objects.filter(bairro=bairro).exclude(pk=alvo.pk).delete()
    return alvo


def executar(apps, schema_editor):
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    mapeamento = carregar_mapeamento_autoritativo()
    processados = set()

    # 1) Corrige todos os bairros que possuem fonte territorial autoritativa.
    for (municipio_nome, bairro_nome), unidade_chave in mapeamento.items():
        municipio = localizar_municipio(Municipio, municipio_nome)
        if municipio is None:
            continue

        bairro = localizar_bairro(Bairro, municipio, bairro_nome)
        if bairro is None:
            bairro = Bairro.objects.create(
                municipio=municipio,
                nome=bairro_nome,
                ativo=True,
            )

        unidade = localizar_unidade(Unidade, unidade_chave)
        ajustar_bairro(AreaResponsabilidade, bairro, unidade)
        processados.add(bairro.id)

    # 2) Faz uma segunda passada em registros fora da fonte autoritativa.
    #    Se houver duplicidade, só resolve automaticamente quando a unidade
    #    municipal padrão identifica inequivocamente uma das áreas.
    inconsistencias = []

    for bairro in Bairro.objects.filter(ativo=True).order_by("municipio_id", "id"):
        areas = list(
            AreaResponsabilidade.objects
            .filter(bairro=bairro)
            .select_related("unidade")
            .order_by("id")
        )

        if len(areas) == 1:
            if not areas[0].ativo:
                areas[0].ativo = True
                areas[0].save(update_fields=["ativo"])
            continue

        if len(areas) == 0:
            inconsistencias.append(
                f"{bairro.municipio.nome} / {bairro.nome}: sem unidade responsável"
            )
            continue

        unidade_padrao_id = bairro.municipio.unidade_responsavel_id
        candidatas = [
            area for area in areas
            if unidade_padrao_id and area.unidade_id == unidade_padrao_id
        ]

        if len(candidatas) == 1:
            ajustar_bairro(AreaResponsabilidade, bairro, candidatas[0].unidade)
            continue

        unidades = ", ".join(
            f"{area.unidade_id}:{area.unidade.nome}" for area in areas
        )
        inconsistencias.append(
            f"{bairro.municipio.nome} / {bairro.nome}: múltiplas unidades ({unidades})"
        )

    if inconsistencias:
        amostra = "\n".join(inconsistencias[:50])
        restante = len(inconsistencias) - min(len(inconsistencias), 50)
        sufixo = f"\n... e mais {restante}." if restante else ""
        raise RuntimeError(
            "A limpeza territorial foi interrompida por inconsistências que não podem ser resolvidas com segurança.\n"
            "Nenhum registro deve ser escolhido por chute. Corrija a fonte territorial e execute novamente.\n"
            f"{amostra}{sufixo}"
        )


def desfazer(apps, schema_editor):
    # Não desfazemos a limpeza porque ela corrige dados potencialmente errados.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0016_permitir_exclusao_usuario"),
    ]

    operations = [
        migrations.RunPython(executar, desfazer),
    ]
