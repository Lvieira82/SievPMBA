from django.test import TestCase

from apps.solicitacoes.models import (
    AreaResponsabilidade,
    Bairro,
    COPPM,
    CPR,
    Municipio,
    Unidade,
)
from apps.solicitacoes.territorio import (
    municipio_tem_multiplas_unidades,
    unidade_para_bairro,
    validar_direcionamento,
)


class TerritorioTestCase(TestCase):
    def setUp(self):
        coppm = COPPM.objects.create(nome="COPPM", sigla="COPPM")
        cpr = CPR.objects.create(
            coppm=coppm,
            nome="CPR Teste",
            sigla="CPR-T",
        )
        self.unidade_a = Unidade.objects.create(
            cpr=cpr,
            nome="Unidade A",
            sigla="UA",
            tipo="BPM",
        )
        self.unidade_b = Unidade.objects.create(
            cpr=cpr,
            nome="Unidade B",
            sigla="UB",
            tipo="BPM",
        )
        self.municipio = Municipio.objects.create(
            nome="Município Teste",
            unidade_responsavel=self.unidade_a,
        )
        self.bairro_a = Bairro.objects.create(
            municipio=self.municipio,
            nome="Centro",
        )
        self.bairro_b = Bairro.objects.create(
            municipio=self.municipio,
            nome="Bairro Novo",
        )
        AreaResponsabilidade.objects.create(
            bairro=self.bairro_a,
            unidade=self.unidade_a,
        )
        AreaResponsabilidade.objects.create(
            bairro=self.bairro_b,
            unidade=self.unidade_b,
        )

    def test_municipio_com_duas_unidades_exige_bairro(self):
        self.assertTrue(municipio_tem_multiplas_unidades(self.municipio))
        self.assertIs(self.unidade_b, validar_direcionamento(self.municipio, self.bairro_b))

    def test_bairro_de_outro_municipio_nao_pode_ser_usado(self):
        outro = Municipio.objects.create(nome="Outro Município")
        bairro = Bairro.objects.create(municipio=outro, nome="Centro")

        with self.assertRaises(Exception):
            validar_direcionamento(self.municipio, bairro)

    def test_api_retorna_bairros_e_unidades(self):
        response = self.client.get(
            f"/api/municipios/{self.municipio.id}/bairros/"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["multiplas_unidades"])
        self.assertEqual(len(data["bairros"]), 2)
        self.assertEqual(len(data["unidades"]), 2)

    def test_bairro_com_duplicidade_preserva_unidade_do_municipio(self):
        municipio = Municipio.objects.create(nome="Feira de Santana")
        bairro = Bairro.objects.create(municipio=municipio, nome="Aviário")

        unidade_errada = Unidade.objects.create(
            cpr=self.unidade_a.cpr,
            nome="45ª CIPM/CURAÇÁ",
            sigla="45ª CIPM/CURAÇÁ",
            tipo="CIPM",
        )
        unidade_correta = Unidade.objects.create(
            cpr=self.unidade_a.cpr,
            nome="67ª CIPM/FEIRA DE SANTANA",
            sigla="67ª CIPM/FEIRA DE SANTANA",
            tipo="CIPM",
        )

        AreaResponsabilidade.objects.create(
            bairro=bairro,
            unidade=unidade_errada,
        )
        AreaResponsabilidade.objects.create(
            bairro=bairro,
            unidade=unidade_correta,
        )

        self.assertIs(unidade_correta, unidade_para_bairro(bairro))

        response = self.client.get(
            f"/api/municipios/{municipio.id}/bairros/"
        )
        data = response.json()
        aviario = next(item for item in data["bairros"] if item["nome"] == "Aviário")

        self.assertEqual(
            aviario["unidades"],
            [{"id": unidade_correta.id, "nome": unidade_correta.nome}],
        )
