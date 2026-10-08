from datetime import date

from django.test import SimpleTestCase

from .leitor_datas_robusto import encontrar_todas_datas


class LeitorDatasRobustoTests(SimpleTestCase):
    def datas(self, texto):
        return {item["data"] for item in encontrar_todas_datas(texto)}

    def test_numerico_com_ano_de_dois_digitos(self):
        ano = date.today().year
        assert self.datas("O evento ocorrerá em 07-01-26.") == {date(2026, 1, 7)}
        assert self.datas("O evento ocorrerá em 07/01/26.") == {date(2026, 1, 7)}

    def test_numerico_sem_ano_usa_ano_corrente(self):
        ano = date.today().year
        assert self.datas("O evento ocorrerá em 07-01.") == {date(ano, 1, 7)}
        assert self.datas("O evento ocorrerá em 07/01.") == {date(ano, 1, 7)}

    def test_range_sem_ano_expande_todos_os_dias(self):
        ano = date.today().year
        assert self.datas("O evento será de 07 a 09/01.") == {
            date(ano, 1, 7),
            date(ano, 1, 8),
            date(ano, 1, 9),
        }

    def test_data_por_extenso_sem_ano(self):
        ano = date.today().year
        assert self.datas("O evento será em 07 de janeiro.") == {
            date(ano, 1, 7)
        }
        assert self.datas("O evento será em sete de janeiro.") == {
            date(ano, 1, 7)
        }

    def test_data_por_extenso_com_ano_por_extenso(self):
        assert self.datas(
            "O evento será em sete de janeiro de dois mil e vinte e seis."
        ) == {date(2026, 1, 7)}

    def test_ano_explicito_de_quatro_digitos_prevalece(self):
        assert self.datas("O evento ocorrerá em 07/01/2027.") == {
            date(2027, 1, 7)
        }

    def test_lista_por_extenso(self):
        ano = date.today().year
        assert self.datas("Nos dias 07, 08 e 09 de janeiro.") == {
            date(ano, 1, 7),
            date(ano, 1, 8),
            date(ano, 1, 9),
        }
