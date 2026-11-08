import os
import tempfile
import unittest
from pathlib import Path
try:
    from moto import mock_aws
except ImportError:
    mock_aws=None
from datapipeline.storage import S3Source
from datapipeline.database import Database
from datapipeline.generator import generate
from datapipeline.pipeline import process
from datapipeline.retry import Fault, TemporaryError

@unittest.skipUnless(mock_aws, 'Installer requirements-dev.txt pour Moto')
class S3Tests(unittest.TestCase):
    def setUp(self):
        self.mock=mock_aws(); self.mock.start()
        self.temp=tempfile.TemporaryDirectory()
        self.source=S3Source(None,'test-transactions','testing','testing',delay=0)
        self.source.setup()
        self.paths=generate(Path(self.temp.name)/'input')
        for path in self.paths: self.source.upload(path)
        self.db=Database('sqlite:///'+str(Path(self.temp.name)/'db.sqlite'))
    def tearDown(self):
        self.mock.stop(); self.temp.cleanup()
    def test_s3_read_without_local_files(self):
        for path in self.paths: path.unlink()
        self.assertEqual(process(self.source,self.db)['inserted'],3)
        self.assertEqual(self.db.report()['transactions'],18)
        self.assertEqual(process(self.source,self.db)['skipped'],3)
    def test_retrieval_retry(self):
        self.source.fault=Fault(2)
        process(self.source,self.db)
        self.assertEqual(self.db.report()['transactions'],18)
    def test_retrieval_exhaustion(self):
        self.source.fault=Fault(10)
        with self.assertRaises(TemporaryError): process(self.source,self.db)
        self.assertEqual(self.db.report()['files'],0)
    def test_permanent_access_error(self):
        from botocore.exceptions import ClientError
        error=ClientError({'Error':{'Code':'AccessDenied'},'ResponseMetadata':{'HTTPStatusCode':403}},'GetObject')
        self.assertFalse(self.source.transient(error))
    def test_pagination(self):
        for i in range(1005):
            self.source.client.put_object(Bucket=self.source.bucket,Key=f'incoming/x{i}.csv',Body=b'x')
        self.assertEqual(len(self.source.keys()),1008)

class RealS3Tests(unittest.TestCase):
    @unittest.skipUnless(os.getenv('TEST_S3_ENDPOINT'), 'S3 réel : TEST_S3_ENDPOINT requis')
    def test_real_s3(self):
        with tempfile.TemporaryDirectory() as temp:
            source=S3Source(os.environ['TEST_S3_ENDPOINT'],'ci-integration',
                            os.getenv('S3_ACCESS_KEY','tpaccess'),os.getenv('S3_SECRET_KEY','tpsecret-change-me'),
                            prefix='test/')
            source.setup()
            for path in generate(Path(temp)/'csv'): source.upload(path)
            db=Database('sqlite:///'+str(Path(temp)/'db'))
            source.fault=Fault(2)
            self.assertEqual(process(source,db,delay=0)['inserted'],3)
            self.assertEqual(db.report()['total_cents'],4920003)
