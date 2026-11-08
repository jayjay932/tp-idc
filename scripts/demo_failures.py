"""Exécute vraiment les scénarios et conserve stdout/stderr + codes retour."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from datapipeline.generator import generate
from datapipeline.domain import COLUMNS

def run(name,arguments,expected):
    cmd=[sys.executable,'-m','datapipeline',*arguments]
    completed=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    content='$ python -m datapipeline '+ ' '.join(arguments)+'\n\n'+completed.stdout+completed.stderr
    content+=f'\nEXIT_CODE={completed.returncode} (attendu={expected})\n'
    destination=ROOT/'docs/evidence'/f'{name}.log'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(content,encoding='utf-8')
    print(f'{name}: retour {completed.returncode}, attendu {expected}')
    if completed.returncode != expected: raise RuntimeError(content)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        directory=Path(tmp)/'csv'; paths=generate(directory)
        original=paths[0].read_bytes()
        paths[0].write_bytes(original.replace(b'100.00',b'invalide',1))
        base=['--directory',str(directory),'--database','sqlite:///'+str(Path(tmp)/'failure.db')]
        run('01-invalid-csv',['run',*base],1)
        paths[0].write_bytes(original)
        run('02-corrected',['run',*base],0)
        run('03-replay',['run',*base],0)
        retrybase=['--directory',str(directory),'--database','sqlite:///'+str(Path(tmp)/'retry.db')]
        run('04-db-retry',['run',*retrybase,'--db-failures','2','--delay','0'],0)
        exhausted=['--directory',str(directory),'--database','sqlite:///'+str(Path(tmp)/'exhaust.db')]
        run('05-db-exhausted',['run',*exhausted,'--db-failures','9','--attempts','3','--delay','0'],1)
        run('06-after-exhaustion',['inspect','--database','sqlite:///'+str(Path(tmp)/'exhaust.db')],0)

if __name__=='__main__': main()
