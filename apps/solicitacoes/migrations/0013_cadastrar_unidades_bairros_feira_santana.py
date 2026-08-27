from django.db import migrations


DADOS = [
    ("25º BPM", [
        "Queimadinha", "São João", "Jaiba", "Matinha", "CASEB",
        "Lagoa Grande", "Parque Getulio Vargas", "Cidade Nova", "Parque Ipê",
        "Papagaio", "Mantiba", "Tiquaruçu", "Mangabeira", "Aeroporto",
        "Conceição", "Santo Antonio dos Prazeres", "SIM", "Registro",
        "Lagoa Salgada", "São Roque", "Subaé", "Santa Mônica II", "Chaparral",
    ]),
    ("67ª CIPM", [
        "Tomba", "CIS", "Aviário", "Parque Viver", "Panorama", "Fraternidade",
        "35º BI", "Viveiros", "Ipuaçu", "Humildes", "Limoeiro", "Parque Tamadari",
        "Olhos D`água", "Jardim Acácia", "Sítio Matias", "Chácara São Cosme",
        "Mochila", "Feira X", "Feira VII", "Caboronga", "Liberdade",
    ]),
    ("64ª CIPM", [
        "Santa Mônica", "Capuchinhos", "Ponto Central", "Centro", "Rua Nova",
        "Serraria Brasil", "Cruzeiro", "Tanque da Nação",
    ]),
    ("65ª CIPM", [
        "Baraúnas", "Sobradinho", "Jardim Cruzeiro", "Calumbi", "Pedra do Descanso",
        "Nova Esperança", "Gabriela", "Campo Limpo", "George Americo",
        "Campo do Gado Novo", "Sítio Novo", "Pampalona", "Pedra Ferrada",
        "Asa Branca", "UEFS", "Novo Horizonte", "Maria Quitéria", "São José",
        "Feira VI", "Jaguara",
    ]),
]


def cadastrar(apps, schema_editor):
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    CPR = apps.get_model("solicitacoes", "CPR")

    municipio, _ = Municipio.objects.get_or_create(
        nome="Feira de Santana",
        defaults={"ativo": True},
    )

    cpr = CPR.objects.filter(sigla="CPR-L", ativo=True).first()
    if cpr is None:
        cpr = CPR.objects.filter(ativo=True).first()

    if cpr is None:
        raise RuntimeError("Nenhum CPR ativo encontrado para cadastrar as unidades de Feira de Santana.")

    for sigla_curta, bairros in DADOS:
        nome_unidade = f"{sigla_curta}/FEIRA DE SANTANA"
        unidade, _ = Unidade.objects.get_or_create(
            nome=nome_unidade,
            defaults={
                "cpr": cpr,
                "sigla": nome_unidade,
                "tipo": "BPM" if "BPM" in sigla_curta else "CIPM",
                "telefone": "",
                "email": "",
                "ativo": True,
            },
        )

        # Corrige vínculos de unidades que já existiam.
        alteracoes = {}
        if unidade.cpr_id != cpr.id:
            alteracoes["cpr"] = cpr
        if not unidade.ativo:
            alteracoes["ativo"] = True
        if alteracoes:
            for campo, valor in alteracoes.items():
                setattr(unidade, campo, valor)
            unidade.save(update_fields=list(alteracoes.keys()))

        for nome_bairro in bairros:
            bairro, _ = Bairro.objects.get_or_create(
                municipio=municipio,
                nome=nome_bairro,
                defaults={"ativo": True},
            )
            if not bairro.ativo:
                bairro.ativo = True
                bairro.save(update_fields=["ativo"])

            AreaResponsabilidade.objects.get_or_create(
                bairro=bairro,
                unidade=unidade,
                defaults={"ativo": True},
            )


def remover(apps, schema_editor):
    # Migration de recuperação: não remove dados existentes no reverse.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0012_adicionar_perfil_operador"),
    ]

    operations = [
        migrations.RunPython(cadastrar, remover),
    ]
