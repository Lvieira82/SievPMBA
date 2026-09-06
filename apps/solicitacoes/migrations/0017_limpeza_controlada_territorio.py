import csv
import importlib
import unicodedata
from pathlib import Path

from django.conf import settings
from django.db import migrations


MIGRACAO_TERRITORIAL = "apps.solicitacoes.migrations.0012_aplicar_areas_responsabilidade_csv"
CSV_BAIRROS = "cadastro_bairros_sievpm.csv"
CSV_MUNICIPIOS = "municipios_417_responsabilidade_SIEVPM.csv"


def normalizar(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar_unidade(texto):
    return normalizar(texto).replace("º", "").replace("ª", "").strip()


def carregar_csv_bairros():
    caminho = Path(settings.BASE_DIR) / CSV_BAIRROS
    if not caminho.exists():
        raise RuntimeError(f"CSV de bairros oficial não encontrado: {caminho}")

    linhas = []
    vistos = {}
    with caminho.open("r", encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        campos = {str(c).strip().lower() for c in (leitor.fieldnames or [])}
        obrigatorios = {"municipio", "bairro", "unidade_responsavel"}
        if not obrigatorios.issubset(campos):
            raise RuntimeError(
                "O CSV de bairros precisa conter municipio,bairro,unidade_responsavel."
            )

        for linha in leitor:
            dados = {
                str(k).strip().lower(): (v or "").strip()
                for k, v in linha.items()
            }
            municipio = dados.get("municipio", "")
            bairro = dados.get("bairro", "")
            unidade = dados.get("unidade_responsavel", "")
            if not municipio or not bairro or not unidade:
                raise RuntimeError("O CSV de bairros possui linha incompleta.")

            chave = (normalizar(municipio), normalizar(bairro))
            unidade_norm = normalizar_unidade(unidade)
            anterior = vistos.get(chave)
            if anterior is not None and anterior != unidade_norm:
                raise RuntimeError(
                    f"Conflito no CSV: '{municipio} / {bairro}' aparece com "
                    f"mais de uma unidade responsável."
                )
            if anterior is not None:
                continue
            vistos[chave] = unidade_norm
            linhas.append((municipio, bairro, unidade))

    return linhas


def carregar_csv_municipios():
    caminho = Path(settings.BASE_DIR) / CSV_MUNICIPIOS
    if not caminho.exists():
        raise RuntimeError(f"CSV territorial oficial não encontrado: {caminho}")

    resultado = {}
    with caminho.open("r", encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")
        campos = {str(c).strip().lower() for c in (leitor.fieldnames or [])}
        obrigatorios = {"municipio", "cpr", "unidade", "status"}
        if not obrigatorios.issubset(campos):
            raise RuntimeError(
                "O CSV municipal precisa conter municipio;cpr;unidade;status."
            )
        for linha in leitor:
            dados = {
                str(k).strip().lower(): (v or "").strip()
                for k, v in linha.items()
            }
            municipio = normalizar(dados.get("municipio"))
            if municipio:
                resultado[municipio] = {
                    "unidade": dados.get("unidade", ""),
                    "status": normalizar(dados.get("status")),
                }
    return resultado


def carregar_mapeamento_legado():
    fonte = importlib.import_module(MIGRACAO_TERRITORIAL)
    return {
        (normalizar(municipio), normalizar(bairro)): unidade
        for municipio, bairro, unidade in fonte.DADOS_TERRITORIAIS
    }


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
    candidatos = [
        bairro
        for bairro in Bairro.objects.filter(municipio=municipio).order_by("id")
        if normalizar(bairro.nome) == normalizar(nome)
    ]
    if len(candidatos) > 1:
        raise RuntimeError(
            f"O município '{municipio.nome}' possui bairros duplicados para '{nome}'."
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
        nomes = (unidade.nome, unidade.sigla)
        if any(
            normalizar_unidade(texto) == base
            or normalizar_unidade(texto).startswith(base + "/")
            for texto in nomes
        ):
            candidatos.append(unidade)

    candidatos = {u.id: u for u in candidatos}
    if len(candidatos) == 1:
        return next(iter(candidatos.values()))

    nomes = ", ".join(
        f"{u.id}:{u.nome}{' [inativa]' if not u.ativo else ''}"
        for u in candidatos.values()
    ) or "nenhuma unidade compatível"
    raise RuntimeError(
        f"Não foi possível resolver de forma única a unidade '{nome_unidade}' "
        f"para '{municipio.nome}': {nomes}."
    )


def ajustar_bairro(AreaResponsabilidade, bairro, unidade):
    AreaResponsabilidade.objects.filter(bairro=bairro).delete()
    AreaResponsabilidade.objects.create(
        bairro=bairro,
        unidade=unidade,
        ativo=True,
    )


def executar(apps, schema_editor):
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    bairros_oficiais = carregar_csv_bairros()
    municipios_csv = carregar_csv_municipios()
    mapeamento_legado = carregar_mapeamento_legado()

    municipios_autoritarios = {
        normalizar(municipio) for municipio, _, _ in bairros_oficiais
    }

    for municipio in Municipio.objects.all():
        if normalizar(municipio.nome) in municipios_autoritarios:
            AreaResponsabilidade.objects.filter(bairro__municipio=municipio).delete()

    for municipio_nome, bairro_nome, unidade_nome in bairros_oficiais:
        municipio = localizar_municipio(Municipio, municipio_nome)
        if municipio is None:
            raise RuntimeError(f"Município do CSV não cadastrado: '{municipio_nome}'.")

        bairro = localizar_bairro(Bairro, municipio, bairro_nome)
        if bairro is None:
            bairro = Bairro.objects.create(
                municipio=municipio,
                nome=bairro_nome,
                ativo=True,
            )

        unidade = localizar_unidade(Unidade, municipio, unidade_nome)
        ajustar_bairro(AreaResponsabilidade, bairro, unidade)

    for (municipio_nome, bairro_nome), unidade_nome in mapeamento_legado.items():
        if municipio_nome in municipios_autoritarios:
            continue
        municipio = localizar_municipio(Municipio, municipio_nome)
        if municipio is None:
            continue
        bairro = localizar_bairro(Bairro, municipio, bairro_nome)
        if bairro is None:
            continue
        unidade = localizar_unidade(Unidade, municipio, unidade_nome)
        ajustar_bairro(AreaResponsabilidade, bairro, unidade)

    for municipio in Municipio.objects.filter(ativo=True):
        nome = normalizar(municipio.nome)
        if nome in municipios_autoritarios:
            continue
        registro = municipios_csv.get(nome)
        if not registro or registro["status"] != "MAPEADO":
            continue

        unidade = localizar_unidade(Unidade, municipio, registro["unidade"])
        if municipio.unidade_responsavel_id != unidade.id:
            municipio.unidade_responsavel_id = unidade.id
            municipio.save(update_fields=["unidade_responsavel"])
        for bairro in Bairro.objects.filter(municipio=municipio, ativo=True):
            ajustar_bairro(AreaResponsabilidade, bairro, unidade)


def desfazer(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0016_permitir_exclusao_usuario"),
        ("solicitacoes", "0013_cadastrar_unidades_bairros_feira_santana"),
    ]

    operations = [
        migrations.RunPython(executar, desfazer),
    ]
