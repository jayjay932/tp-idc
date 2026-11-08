"""Orchestration ; fonctions métier indépendantes des entrées/sorties."""
import hashlib
import logging
from .domain import parse_csv, flag_transactions
log = logging.getLogger(__name__)

def process(source, database, fault=None, attempts=4, delay=0.2):
    database.initialize()
    result = {'inserted': 0, 'skipped': 0}
    for key in source.keys():
        content = source.read(key)
        digest = hashlib.sha256(content).hexdigest()
        if database.seen(digest):
            log.info('IGNORÉ (déjà traité) : %s', key)
            result['skipped'] += 1
            continue
        rows = flag_transactions(parse_csv(content))
        inserted = database.insert_file(digest, key, rows, fault, attempts, delay)
        result['inserted' if inserted else 'skipped'] += 1
        log.info('%s : %s (%s transactions)', 'INSÉRÉ' if inserted else 'IGNORÉ', key, len(rows))
    return result
