import csv
from pathlib import Path

from django.db import migrations


def reconstruir_territorio(apps, schema_editor):
    COPPM = apps.get_model("solicitacoes", "COPPM")
    CPR = apps.get_model("solicitacoes", "CPR")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    Municipio = apps.get_model("solicitacoes", "Municipio")

    base_dir = Path(__file__).resolve().parents[3]
    arquivo = base_dir / "municipios_417_responsabilidade_SIEVPM.csv"

    if not arquivo.exists():
        return

    coppm, _ = COPPM.objects.get_or_create(
        sigla="COPPM",
        defaults={
            "nome": "Comando de Operações Policiais Militares",
            "ativo": True,
        },
    )

    with arquivo.open("r", encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f, delimiter=";")

        for linha in leitor:
            municipio_nome = (linha.get("municipio") or "").strip()
            cpr_sigla = (linha.get("cpr") or "").strip()
            unidade_nome = (linha.get("unidade") or "").strip()

            if not cpr_sigla or not unidade_nome:
                continue

            cpr, _ = CPR.objects.get_or_create(
                sigla=cpr_sigla,
                defaults={
                    "nome": cpr_sigla,
                    "coppm": coppm,
                    "ativo": True,
                },
            )

            changed = False
            if not cpr.ativo:
                cpr.ativo = True
                changed = True
            if cpr.coppm_id != coppm.id:
                cpr.coppm_id = coppm.id
                changed = True
            if changed:
                cpr.save(update_fields=["ativo", "coppm"])

            unidade, _ = Unidade.objects.get_or_create(
                cpr=cpr,
                sigla=unidade_nome,
                defaults={
                    "nome": unidade_nome,
                    "tipo": "BPM" if "BPM" in unidade_nome.upper() else "CIPM",
                    "telefone": "",
                    "email": "",
                    "ativo": True,
                },
            )

            if not unidade.ativo:
                unidade.ativo = True
                unidade.save(update_fields=["ativo"])

            if municipio_nome:
                municipio, _ = Municipio.objects.get_or_create(
                    nome=municipio_nome,
                )
                if municipio.unidade_responsavel_id != unidade.id:
                    municipio.unidade_responsavel_id = unidade.id
                    municipio.save(update_fields=["unidade_responsavel"])


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0014_reativar_estrutura_territorial"),
    ]

    operations = [
        migrations.RunPython(
            reconstruir_territorio,
            migrations.RunPython.noop,
        ),
    ]
