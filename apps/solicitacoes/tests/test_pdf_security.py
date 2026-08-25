from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from apps.solicitacoes.pdf_security import validar_pdf_upload


class PdfSecurityTestCase(SimpleTestCase):
    def test_rejeita_arquivo_que_nao_e_pdf(self):
        arquivo = SimpleUploadedFile(
            "arquivo.pdf",
            b"nao e um pdf",
            content_type="application/pdf",
        )

        with self.assertRaises(ValidationError):
            validar_pdf_upload(arquivo)
