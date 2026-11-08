"""Vérifie la base après la démo Compose, y compris après rejouement."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datapipeline.database import Database
report=Database(os.environ['DATABASE_URL']).report()
assert report['files']==3,report
assert report['transactions']==18,report
assert report['flagged']==6,report
assert report['total_cents']==4920003,report
print('STACK OK : 18 transactions, 6 flags, 49 200.03 EUR, aucun doublon')
