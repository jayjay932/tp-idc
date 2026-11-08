import hashlib
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datapipeline.database import Database
from datapipeline.domain import COLUMNS, ValidationError, parse_csv, flag_transactions, sum_by, to_csv
from datapipeline.generator import generate, sample_rows, A, B, C
from datapipeline.pipeline import process
from datapipeline.retry import Fault, TemporaryError, retry
from datapipeline.storage import LocalSource

class DomainTests(unittest.TestCase):
    def test_generation_and_round_trip(self):
        for batch in range(3):
            self.assertEqual(parse_csv(to_csv(sample_rows(batch))), sample_rows(batch))
    def test_boundary_and_purity(self):
        original = sample_rows()
        output = flag_transactions(original)
        self.assertEqual([r.flag for r in output], [False, False, True, False, True, False])
        self.assertTrue(all(not r.flag for r in original))
        self.assertEqual(flag_transactions(original), output)
    def test_three_aggregations(self):
        rows = sample_rows()
        self.assertEqual(sum_by(rows,'iban_origine'), {A:1130001, B:510000})
        self.assertEqual(sum_by(rows,'banque_source'), {'Banque A':1130001,'Banque B':510000})
        self.assertEqual(sum_by(rows,'iban_destinataire'), {B:1010001,C:630000})
    def test_invalid_amounts(self):
        content = to_csv(sample_rows()).decode()
        for invalid in ('-1', '0', 'NaN', 'Infinity', '12.345', '1.000', '1e3', 'abc'):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                parse_csv(content.replace(',100.00', ','+invalid,1).encode())
    def test_empty_and_invalid_header(self):
        for content in (b'', b'x,y\n1,2', (','.join(COLUMNS)+'\n').encode(), b'\xff'):
            with self.assertRaises(ValidationError): parse_csv(content)
    def test_invalid_fields(self):
        for old,new in [(A,A[:-1]+'7'),('2026-09-12T14:00:00+00:00','2026-09-12'),(',FR,',',ZZ,')]:
            with self.assertRaises(ValidationError):
                parse_csv(to_csv(sample_rows()).replace(old.encode(),new.encode()))
    def test_extra_column(self):
        with self.assertRaises(ValidationError):
            parse_csv(to_csv(sample_rows()).replace(b'100.00',b'100.00,unexpected',1))

class RetryTests(unittest.TestCase):
    def test_backoff(self):
        fault=Fault(2); waits=[]
        self.assertIsNone(retry(fault.trigger, attempts=3, delay=.5, sleep=waits.append))
        self.assertEqual(waits,[.5,1])
    def test_exhaustion(self):
        with self.assertRaises(TemporaryError): retry(Fault(4).trigger,attempts=3,delay=0)
    def test_permanent_error_is_not_retried(self):
        calls=[]
        def fail():
            calls.append(1); raise ValueError('permanent')
        with self.assertRaises(ValueError): retry(fail,delay=0)
        self.assertEqual(len(calls),1)

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.directory=Path(self.temp.name)/'csv'
        self.db=Database('sqlite:///'+str(Path(self.temp.name)/'db.sqlite'))
        generate(self.directory)
        self.source=LocalSource(self.directory)
    def tearDown(self): self.temp.cleanup()
    def test_pipeline_and_values_in_database(self):
        self.assertEqual(process(self.source,self.db),{'inserted':3,'skipped':0})
        self.assertEqual(self.db.report(),{
            'files':3,'transactions':18,'flagged':6,'total_cents':4920003,
            'sent_by_iban':{A:3390003,B:1530000},
            'sent_by_bank':{'Banque A':3390003,'Banque B':1530000},
            'received_by_iban':{B:3030003,C:1890000}})
    def test_retry_rolls_back_before_reinsertion(self):
        process(self.source,self.db,Fault(2),delay=0)
        self.assertEqual(self.db.report()['transactions'],18)
        self.assertEqual(self.db.report()['files'],3)
    def test_exhaustion_rolls_back_everything(self):
        with self.assertRaises(TemporaryError): process(self.source,self.db,Fault(10),attempts=3,delay=0)
        self.assertEqual(self.db.report()['transactions'],0)
        self.assertEqual(self.db.report()['files'],0)
    def test_replay_and_renamed_copy(self):
        process(self.source,self.db)
        original=next(self.directory.glob('*.csv'))
        (self.directory/'renamed.csv').write_bytes(original.read_bytes())
        self.assertEqual(process(self.source,self.db),{'inserted':0,'skipped':4})
        self.assertEqual(self.db.report()['transactions'],18)
    def test_bad_file_is_not_marked(self):
        for path in self.directory.glob('*.csv'): path.unlink()
        (self.directory/'bad.csv').write_text('wrong,header\n1,2')
        with self.assertRaises(ValidationError): process(self.source,self.db)
        self.assertEqual(self.db.report()['files'],0)
    def test_concurrent_same_file(self):
        self.db.initialize()
        rows=flag_transactions(sample_rows())
        def insert(_): return self.db.insert_file('same-hash','same.csv',rows,delay=.01)
        with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(insert,range(4)))
        self.assertEqual(sum(results),1)
        self.assertEqual(self.db.report()['transactions'],6)
    def test_sql_constraint_flag(self):
        self.db.initialize()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.insert_file('bad','bad.csv',sample_rows(),delay=0)
        self.assertEqual(self.db.report()['files'],0)

class RealPostgresTests(unittest.TestCase):
    @unittest.skipUnless(os.getenv('TEST_POSTGRES_URL'), 'PostgreSQL réel : TEST_POSTGRES_URL requis')
    def test_postgres_transaction_and_retry(self):
        db=Database(os.environ['TEST_POSTGRES_URL']); db.initialize()
        # Base de test exclusivement : vider uniquement si la variable dédiée est définie.
        with db.connect() as conn:
            conn.execute('DELETE FROM transactions'); conn.execute('DELETE FROM processed_files')
        with tempfile.TemporaryDirectory() as temp:
            generate(temp); source=LocalSource(temp)
            process(source,db,Fault(2),delay=0)
            self.assertEqual(db.report()['transactions'],18)
            self.assertEqual(db.report()['total_cents'],4920003)
            self.assertEqual(process(source,db)['skipped'],3)
