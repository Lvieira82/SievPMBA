import importlib
import unicodedata

from django.db import migrations


MIGRACAO_TERRITORIAL = "apps.solicitacoes.migrations.0012_aplicar_areas_responsabilidade_csv"
MIGRACAO_FEIRA = "apps.solicitacoes.migrations.0013_cadastrar_unidades_bairros_feira_santana"


def normalizar(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar_unidade(texto):
    return normalizar(texto).replace("º", "").replace("ª", "").strip()


def carregar_mapeamento_autoritativo():
    """MUNICÍPIO + BAIRRO é sempre a chave territorial.

    Para Feira de Santana, a migration 0013 contém os nomes completos das
    unidades e prevalece sobre a nomenclatura antiga da migration 0012.
    Isso é importante porque o banco pode possuir, por legado, tanto
    "67ª CIPM" quanto "67ª CIPM/FEIRA DE SANTANA".
    """
    fonte = importlib.import_module(MIGRACAO_TERRITORIAL)
    mapeamento = {}

    for municipio, bairro, unidade in fonte.DADOS_TERRITORIAIS:
        mapeamento[(normalizar(municipio), normalizar(bairro))] = unidade

    feira = importlib.import_module(MIGRACAO_FEIRA)
    for nome_unidade, bairros in feira.BAIRROS.items():
        for bairro in bairros:
            mapeamento[(normalizar("Feira de Santana"), normalizar(bairro))] = nome_unidade

    return mapeamento


def localizar_municipio(Municipio, nome):
    candidatos = [
        municipio
        for municipio in Municipio.objects.all()
        if normalizar(municipio.nome) == normalizar(nome)
    ]
    if len(candidatos) > 1:
        raise RuntimeError(f"Existem municípios duplicados para '{nome}'.")
    return candidatos[0] if candidatos else None


def localizar_bairro(Bairro, municipio, nome):
    candidatos = list(
        Bairro.objects.filter(municipio=municipio, nome__iexact=nome).order_by("id")
    )
    if len(candidatos) == 1:
        return candidatos[0]
    if len(candidatos) > 1:
        raise RuntimeError(
            f"O município '{municipio.nome}' possui bairros duplicados chamados '{nome}'."
        )

    candidatos = [
        bairro
        for bairro in Bairro.objects.filter(municipio=municipio).order_by("id")
        if normalizar(bairro.nome) == normalizar(nome)
    ]
    if len(candidatos) > 1:
        raise RuntimeError(
            f"O município '{municipio.nome}' possui bairros equivalentes duplicados para '{nome}'."
        )
    return candidatos[0] if candidatos else None


def localizar_unidade(Unidade, municipio, nome_unidade):
    alvo = normalizar_unidade(nome_unidade)

    # 1. Primeiro tenta o nome/sigla completo entre as unidades ativas.
    exatas_ativas = []
    exatas_inativas = []
    for unidade in Unidade.objects.all().order_by("id"):
        nomes = {
            normalizar_unidade(unidade.nome),
            normalizar_unidade(unidade.sigla),
        }
        if alvo in nomes:
            if unidade.ativo:
                exatas_ativas.append(unidade)
            else:
                exatas_inativas.append(unidade)

    if len(exatas_ativas) == 1:
        return exatas_ativas[0]
    if len(exatas_ativas) > 1:
        raise RuntimeError(
            f"Existem unidades ativas duplicadas para '{nome_unidade}' em '{municipio.nome}'."
        )
    if len(exatas_inativas) == 1:
        # Uma unidade territorial pode estar desativada administrativamente.
        # A migração preserva esse estado; não reativa cadastros por conta própria.
        return exatas_inativas[0]
    if len(exatas_inativas) > 1:
        raise RuntimeError(
            f"Existem unidades inativas duplicadas para '{nome_unidade}' em '{municipio.nome}'."
        )

    # 2. Para fontes antigas como "67ª CIPM", permite prefixo somente quando
    #    há uma única unidade compatível no CPR do município.
    base = alvo.split("/", 1)[0].strip()
    candidatos = []
    for unidade in Unidade.objects.all().select_related("cpr"):
        for texto in (unidade.nome, unidade.sigla):
            normalizado = normalizar_unidade(texto)
            if normalizado == base or normalizado.startswith(base + "/"):
                candidatos.append(unidade)
                break

    candidatos_unicos = {u.id: u for u in candidatos}
    if municipio.unidade_responsavel_id:
        mesma_cadeia = {
            u.id: u
            for u in candidatos_unicos.values()
            if u.cpr_id == municipio.unidade_responsavel.cpr_id
        }
        if len(mesma_cadeia) == 1:
            return next(iter(mesma_cadeia.values()))

    if len(candidatos_unicos) == 1:
        return next(iter(candidatos_unicos.values()))

    nomes = ", ".join(
        f"{u.id}:{u.nome}{' [inativa]' if not u.ativo else ''}" for u in candidatos_unicos.values()
    ) or "nenhuma unidade compatível"
    raise RuntimeError(
        f"Não foi possível resolver de forma única a unidade '{nome_unidade}' "
        f"para '{municipio.nome}': {nomes}."
    )


def ajustar_bairro(AreaResponsabilidade, bairro, unidade):
    areas = list(
        AreaResponsabilidade.objects.filter(bairro=bairro).order_by("id")
    )

    alvo = next((area for area in areas if area.unidade_id == unidade.id), None)
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
        alvo.unidade_id = unidade.id
        alvo.ativo = True
        alvo.save(update_fields=["unidade", "ativo"])

    AreaResponsabilidade.objects.filter(bairro=bairro).exclude(pk=alvo.pk).delete()


def executar(apps, schema_editor):
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    mapeamento = carregar_mapeamento_autoritativo()
    bairros_fonte = set()

    # Limpeza da fonte autoritativa: homônimos são tratados por município.
    for (municipio_nome, bairro_nome), unidade_nome in mapeamento.items():
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

        unidade = localizar_unidade(Unidade, municipio, unidade_nome)
        ajustar_bairro(AreaResponsabilidade, bairro, unidade)
        bairros_fonte.add(bairro.id)

    # Fora da fonte autoritativa, nunca inventa uma associação.
    # Duplicidades só são resolvidas quando a unidade municipal padrão é
    # inequivocamente uma das associações existentes.
    for bairro in Bairro.objects.filter(ativo=True).order_by("municipio_id", "id"):
        areas = list(
            AreaResponsabilidade.objects
            .filter(bairro=bairro)
            .select_related("unidade")
            .order_by("id")
        )

        if len(areas) <= 1:
            if len(areas) == 1 and not areas[0].ativo:
                areas[0].ativo = True
                areas[0].save(update_fields=["ativo"])
            continue

        padrao = bairro.municipio.unidade_responsavel_id
        candidatas = [area for area in areas if padrao and area.unidade_id == padrao]
        if len(candidatas) == 1:
            ajustar_bairro(AreaResponsabilidade, bairro, candidatas[0].unidade)
            continue

        unidades = ", ".join(f"{area.unidade_id}:{area.unidade.nome}" for area in areas)
        raise RuntimeError(
            "Duplicidade territorial sem fonte autoritativa para resolução: "
            f"{bairro.municipio.nome} / {bairro.nome} → {unidades}. "
            "A implantação foi interrompida para não escolher uma unidade por chute."
        )


def desfazer(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0016_permitir_exclusao_usuario"),
    ]

    operations = [
        migrations.RunPython(executar, desfazer),
    ]
