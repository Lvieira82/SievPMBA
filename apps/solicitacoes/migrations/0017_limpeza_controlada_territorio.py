import csv
import importlib
import unicodedata
from pathlib import Path

from django.conf import settings
from django.db import migrations


MIGRACAO_TERRITORIAL = "apps.solicitacoes.migrations.0012_aplicar_areas_responsabilidade_csv"
MIGRACAO_FEIRA = "apps.solicitacoes.migrations.0013_cadastrar_unidades_bairros_feira_santana"
CSV_TERRITORIAL = "municipios_417_responsabilidade_SIEVPM.csv"


def normalizar(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar_unidade(texto):
    return normalizar(texto).replace("º", "").replace("ª", "").strip()


def carregar_csv_oficial():
    caminho = Path(settings.BASE_DIR) / CSV_TERRITORIAL
    if not caminho.exists():
        raise RuntimeError(f"CSV territorial oficial não encontrado: {caminho}")

    resultado = {}
    with caminho.open("r", encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")
        campos = {str(c).strip().lower() for c in (leitor.fieldnames or [])}
        obrigatorios = {"municipio", "cpr", "unidade", "status"}
        if not obrigatorios.issubset(campos):
            raise RuntimeError(
                "O CSV territorial oficial precisa conter municipio;cpr;unidade;status."
            )

        for linha in leitor:
            dados = {
                str(k).strip().lower(): (v or "").strip()
                for k, v in linha.items()
            }
            municipio = normalizar(dados.get("municipio"))
            if municipio:
                resultado[municipio] = {
                    "cpr": dados.get("cpr", ""),
                    "unidade": dados.get("unidade", ""),
                    "status": normalizar(dados.get("status")),
                }
    return resultado


def carregar_mapeamento_bairros():
    """Fonte detalhada de bairro; sempre chaveada por município + bairro."""
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

    exatas = []
    for unidade in Unidade.objects.all().order_by("id"):
        if alvo in {
            normalizar_unidade(unidade.nome),
            normalizar_unidade(unidade.sigla),
        }:
            exatas.append(unidade)

    if len(exatas) == 1:
        return exatas[0]
    if len(exatas) > 1:
        raise RuntimeError(
            f"Existem unidades duplicadas para '{nome_unidade}' em '{municipio.nome}'."
        )

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
        f"{u.id}:{u.nome}{' [inativa]' if not u.ativo else ''}"
        for u in candidatos_unicos.values()
    ) or "nenhuma unidade compatível"
    raise RuntimeError(
        f"Não foi possível resolver de forma única a unidade '{nome_unidade}' "
        f"para '{municipio.nome}': {nomes}."
    )


def localizar_ou_criar_unidade_feira(apps, Unidade, CPR, COPPM, nome_unidade, sigla, tipo):
    existente = list(
        Unidade.objects.filter(nome__iexact=nome_unidade).order_by("id")
    )
    if len(existente) == 1:
        return existente[0]
    if len(existente) > 1:
        raise RuntimeError(f"Unidade duplicada: '{nome_unidade}'.")

    coppm = COPPM.objects.filter(sigla="COPPM").first()
    if coppm is None:
        coppm = COPPM.objects.create(
            sigla="COPPM",
            nome="Comando de Operações Policiais Militares",
            ativo=True,
        )

    cpr = CPR.objects.filter(sigla="CPR-L").first()
    if cpr is None:
        cpr = CPR.objects.create(
            sigla="CPR-L",
            nome="Comando de Policiamento Regional Leste",
            coppm=coppm,
            ativo=True,
        )

    return Unidade.objects.create(
        cpr=cpr,
        nome=nome_unidade,
        sigla=sigla,
        tipo=tipo,
        telefone="",
        email="",
        ativo=True,
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
    CPR = apps.get_model("solicitacoes", "CPR")
    COPPM = apps.get_model("solicitacoes", "COPPM")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    csv_oficial = carregar_csv_oficial()
    mapeamento_bairros = carregar_mapeamento_bairros()

    # Garante as quatro unidades detalhadas de Feira, mesmo que algum cadastro
    # antigo tenha sido removido manualmente.
    feira = importlib.import_module(MIGRACAO_FEIRA)
    for nome, sigla, tipo in feira.UNIDADES:
        localizar_ou_criar_unidade_feira(
            apps, Unidade, CPR, COPPM, nome, sigla, tipo
        )

    # 1) Fonte detalhada: município + bairro. Para homônimos, o município é
    # parte obrigatória da chave e nenhuma associação de outra cidade entra.
    for (municipio_nome, bairro_nome), unidade_nome in mapeamento_bairros.items():
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

    # 2) CSV oficial: municípios MAPEADOS possuem uma única unidade. Todos os
    # bairros desse município recebem essa unidade. Municípios MULTIPLA não
    # são resolvidos por chute: permanecem somente com o mapeamento detalhado.
    for municipio in Municipio.objects.filter(ativo=True).order_by("id"):
        registro = csv_oficial.get(normalizar(municipio.nome))
        if not registro or registro["status"] != "MAPEADO":
            continue

        unidade = localizar_unidade(Unidade, municipio, registro["unidade"])
        if municipio.unidade_responsavel_id != unidade.id:
            municipio.unidade_responsavel_id = unidade.id
            municipio.save(update_fields=["unidade_responsavel"])

        for bairro in Bairro.objects.filter(municipio=municipio, ativo=True):
            ajustar_bairro(AreaResponsabilidade, bairro, unidade)

    # 3) Qualquer duplicidade que não possua fonte autoritativa é eliminada,
    # deixando o bairro sem roteamento em vez de escolher uma unidade errada.
    for bairro in Bairro.objects.filter(ativo=True).order_by("municipio_id", "id"):
        areas = list(
            AreaResponsabilidade.objects.filter(bairro=bairro).order_by("id")
        )
        if len(areas) <= 1:
            continue

        if (normalizar(bairro.municipio.nome), normalizar(bairro.nome)) in mapeamento_bairros:
            continue

        AreaResponsabilidade.objects.filter(bairro=bairro).delete()


def desfazer(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0016_permitir_exclusao_usuario"),
    ]

    operations = [
        migrations.RunPython(executar, desfazer),
    ]
