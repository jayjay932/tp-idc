import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datapipeline.extraction import records_to_csv, ocr, slm
from datapipeline.domain import COLUMNS, ValidationError, parse_csv
from datapipeline.generator import A, B

RECORD={'datetime_transaction':'2026-09-12T14:30:00+00:00','iban_origine':A,
        'pays_source':'FR','banque_source':'BanqueA','iban_destinataire':B,
        'pays_destinataire':'DE','montant':'6200.00'}

class ExtractionTests(unittest.TestCase):
    def test_validated_common_format(self):
        self.assertEqual(parse_csv(records_to_csv([RECORD]))[0].montant_cents,620000)
    def test_missing_not_invented(self):
        incomplete=dict(RECORD); incomplete['banque_source']=''
        with self.assertRaises(ValidationError): records_to_csv([incomplete])
    def test_ollama_contract_mock(self):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'response':json.dumps({'transactions':[RECORD]})}).encode()
        with patch('urllib.request.urlopen',return_value=response) as request:
            output=slm('transaction source')
        self.assertEqual(len(parse_csv(output)),1)
        payload=json.loads(request.call_args.args[0].data)
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['format']['type'],'object')
    def test_ocr_bad_text_rejected(self):
        result=MagicMock(stdout='unreadable')
        with patch('subprocess.run',return_value=result), self.assertRaises(ValidationError):
            ocr('test.png')
    @unittest.skipUnless(shutil.which('tesseract'), 'Tesseract absent')
    def test_real_ocr_sample(self):
        path=Path(__file__).resolve().parents[1]/'examples/transaction.png'
        if not path.exists(): self.skipTest('Générer examples/transaction.png')
        self.assertEqual(parse_csv(ocr(path))[0].montant_cents,620000)
    @unittest.skipUnless(os.getenv('TEST_OLLAMA_URL'),'SLM réel : TEST_OLLAMA_URL requis')
    def test_real_slm(self):
        text=(Path(__file__).resolve().parents[1]/'examples/transaction.txt').read_text()
        rows=parse_csv(slm(text,os.environ['TEST_OLLAMA_URL'],os.getenv('SLM_MODEL','qwen2.5:1.5b')))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].montant_cents,620000)
        self.assertEqual(rows[0].iban_origine,A)
