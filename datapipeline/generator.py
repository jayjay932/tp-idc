"""Jeu déterministe : trois fichiers de six transactions, sans hasard."""
from pathlib import Path
from .domain import Transaction, to_csv

A = "FR1420041010050500013M02606"
B = "DE89370400440532013000"
C = "GB82WEST12345698765432"
AMOUNTS = (10000, 500000, 500001, 9999, 620000, 1)

def sample_rows(batch=0):
    rows = []
    for i, cents in enumerate(AMOUNTS):
        origin, source, bank = (A, 'FR', 'Banque A') if i % 2 == 0 else (B, 'DE', 'Banque B')
        destination, country = (B, 'DE') if i < 3 else (C, 'GB')
        rows.append(Transaction(f'2026-09-{12+batch:02d}T14:{i:02d}:00+00:00', origin,
                                source, bank, destination, country, cents))
    return tuple(rows)

def generate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for batch in range(3):
        path = directory / f'transactions_{batch+1:02d}.csv'
        path.write_bytes(to_csv(sample_rows(batch)))
        paths.append(path)
    return paths
