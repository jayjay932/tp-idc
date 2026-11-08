"""Adaptateurs d'entrée : local et vrai client S3 (boto3)."""
from pathlib import Path
from .retry import retry, TemporaryError

class LocalSource:
    def __init__(self, directory):
        self.directory = Path(directory)
    def keys(self):
        if not self.directory.is_dir():
            raise FileNotFoundError(self.directory)
        return sorted(str(p) for p in self.directory.glob('*.csv'))
    def read(self, key):
        return Path(key).read_bytes()

class S3Source:
    def __init__(self, endpoint, bucket, access_key, secret_key, prefix='incoming/', fault=None,
                 attempts=4, delay=0.2):
        import boto3
        from botocore.config import Config
        self.client = boto3.client('s3', endpoint_url=endpoint, aws_access_key_id=access_key,
                                  aws_secret_access_key=secret_key, region_name='us-east-1',
                                  config=Config(s3={'addressing_style':'path'}, connect_timeout=3,
                                                read_timeout=10, retries={'total_max_attempts':1}))
        self.bucket, self.prefix, self.fault = bucket, prefix, fault
        self.attempts, self.delay = attempts, delay

    @staticmethod
    def transient(exc):
        from botocore.exceptions import ClientError, ConnectionClosedError, EndpointConnectionError, HTTPClientError
        if isinstance(exc, (TemporaryError, EndpointConnectionError, ConnectionClosedError, HTTPClientError)):
            return True
        if isinstance(exc, ClientError):
            response = exc.response
            return response.get('ResponseMetadata',{}).get('HTTPStatusCode',0) >= 500 or response['Error']['Code'] in (
                'SlowDown','RequestTimeout','NoSuchKey','404')
        return False

    def call(self, operation, *, attempts=None, label='S3'):
        return retry(operation, attempts=attempts or self.attempts, delay=self.delay,
                     transient=self.transient, label=label)

    def setup(self):
        from botocore.exceptions import ClientError
        def ensure():
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except ClientError as exc:
                if exc.response['Error']['Code'] not in ('404','NoSuchBucket','NotFound'):
                    raise
                self.client.create_bucket(Bucket=self.bucket)
        self.call(ensure, attempts=30, label='préparation bucket')

    def upload(self, path):
        key = self.prefix + Path(path).name
        content = Path(path).read_bytes()
        self.call(lambda: self.client.put_object(Bucket=self.bucket, Key=key, Body=content))
        # Vérification par relecture réelle des octets, pas seulement par listing.
        if self.read(key) != content:
            raise RuntimeError(f'Upload S3 corrompu : {key}')
        return key

    def keys(self):
        def listing():
            paginator = self.client.get_paginator('list_objects_v2')
            return sorted(obj['Key'] for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix)
                          for obj in page.get('Contents',[]) if obj['Key'].endswith('.csv'))
        return self.call(listing, label='liste S3')

    def read(self, key):
        def fetch():
            if self.fault:
                self.fault.trigger()
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response['Body']
            try:
                return body.read()
            finally:
                body.close()
        return self.call(fetch, label=f'lecture S3 {key}')
