"""CLI : python -m datapipeline --help."""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from .database import Database
from .generator import generate
from .storage import LocalSource, S3Source
from .pipeline import process
from .retry import Fault

def parser():
    p = argparse.ArgumentParser(description='TP IDC : pipeline financière CI/CD')
    p.add_argument('command', choices=['generate','run','demo','inspect','upload','ocr','slm','watch'])
    p.add_argument('--source', choices=['local','s3'], default='local')
    p.add_argument('--directory', default='data/incoming')
    p.add_argument('--database', default=os.getenv('DATABASE_URL','sqlite:///data/pipeline.db'))
    p.add_argument('--db-failures',type=int,default=0)
    p.add_argument('--s3-failures',type=int,default=0)
    p.add_argument('--attempts',type=int,default=4)
    p.add_argument('--delay',type=float,default=0.2)
    p.add_argument('--input')
    p.add_argument('--output',default='data/extracted.csv')
    p.add_argument('--interval',type=int,default=60)
    return p

def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if args.attempts < 1 or args.delay < 0 or min(args.db_failures,args.s3_failures) < 0 or args.interval < 1:
        parser().error('Paramètres de retry/intervalle invalides')
    try:
        if args.command in ('ocr','slm'):
            from .extraction import ocr, slm
            if not args.input:
                raise ValueError('--input obligatoire')
            content = ocr(args.input) if args.command == 'ocr' else slm(
                Path(args.input).read_text(encoding='utf-8'), os.getenv('OLLAMA_URL','http://localhost:11434'),
                os.getenv('SLM_MODEL','qwen2.5:1.5b'))
            path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(content)
            print(f'CSV extrait et validé : {path}')
            return 0
        if args.command == 'generate':
            print(json.dumps([str(p) for p in generate(args.directory)])); return 0
        db = Database(args.database)
        if args.command == 'inspect':
            db.initialize(); print(json.dumps(db.report(),indent=2)); return 0
        paths = generate(args.directory) if args.command == 'demo' else []
        if args.source == 's3' or args.command == 'upload':
            source = S3Source(os.getenv('S3_ENDPOINT','http://localhost:9000'),
                              os.getenv('S3_BUCKET','transactions'), os.getenv('S3_ACCESS_KEY','tpaccess'),
                              os.getenv('S3_SECRET_KEY','tpsecret-change-me'),
                              prefix=os.getenv('S3_PREFIX','incoming/'), attempts=args.attempts, delay=args.delay)
            source.setup()
            if paths or args.command == 'upload':
                for path in paths or sorted(Path(args.directory).glob('*.csv')):
                    print('Upload vérifié : '+source.upload(path))
            source.fault = Fault(args.s3_failures)
        else:
            source = LocalSource(args.directory)
        if args.command == 'upload':
            return 0
        fault=Fault(args.db_failures)
        while True:
            print(json.dumps(process(source,db,fault,args.attempts,args.delay)),flush=True)
            print(json.dumps(db.report(),indent=2),flush=True)
            if args.command != 'watch':
                break
            time.sleep(args.interval)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        logging.exception('PIPELINE EN ÉCHEC')
        return 1

if __name__ == '__main__':
    sys.exit(main())
