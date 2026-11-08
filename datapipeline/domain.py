"""Validation et transformations pures : aucun accès disque, réseau ou base."""
import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, replace

COLUMNS = ("datetime_transaction", "iban_origine", "pays_source", "banque_source",
           "iban_destinataire", "pays_destinataire", "montant")

class ValidationError(ValueError):
    pass

@dataclass(frozen=True)
class Transaction:
    datetime_transaction: str
    iban_origine: str
    pays_source: str
    banque_source: str
    iban_destinataire: str
    pays_destinataire: str
    montant_cents: int
    flag: bool = False

def validate_record(row):
    if set(row) != set(COLUMNS):
        raise ValidationError("Colonnes incorrectes : attendu " + ", ".join(COLUMNS))
    if any(not isinstance(v, str) or not v.strip() for v in row.values()):
        raise ValidationError("Champ absent ou vide")
    row = {k: v.strip() for k, v in row.items()}
    try:
        when = datetime.fromisoformat(row["datetime_transaction"])
        if "T" not in row["datetime_transaction"] or when.tzinfo is None:
            raise ValueError("timezone manquante")
    except ValueError as exc:
        raise ValidationError("Date ISO 8601 avec fuseau requise") from exc
    for field in ("iban_origine", "iban_destinataire"):
        iban = row[field]
        if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", iban):
            raise ValidationError(f"Format IBAN invalide : {field}")
        # ISO 13616 : contrôle modulo 97 (ne vérifie pas l'existence du compte).
        expanded = ''.join(str(ord(c)-55) if c.isalpha() else c for c in iban[4:]+iban[:4])
        if int(expanded) % 97 != 1:
            raise ValidationError(f"Clé IBAN invalide : {field}")
    for field in ("pays_source", "pays_destinataire"):
        if not re.fullmatch(r"[A-Z]{2}", row[field]):
            raise ValidationError(f"Code pays à deux lettres requis : {field}")
    if row['iban_origine'][:2] != row['pays_source'] or row['iban_destinataire'][:2] != row['pays_destinataire']:
        raise ValidationError("Le pays doit correspondre au préfixe de l'IBAN")
    try:
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?', row['montant']):
            raise ValueError('format décimal invalide')
        amount = Decimal(row['montant'])
        if not amount.is_finite() or amount <= 0 or amount > Decimal('999999999999.99'):
            raise ValueError('montant hors limites')
        if amount * 100 != (amount * 100).to_integral_value():
            raise ValueError('plus de deux décimales')
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Montant positif avec au maximum deux décimales requis") from exc
    return Transaction(*(row[k] for k in COLUMNS[:-1]), montant_cents=int(amount * 100))

def parse_csv(content):
    try:
        stream = io.StringIO(content.decode('utf-8-sig'), newline='')
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValidationError("En-tête CSV incorrect")
        rows = []
        for number, row in enumerate(reader, 2):
            try:
                rows.append(validate_record(row))
            except ValidationError as exc:
                raise ValidationError(f"Ligne {number} : {exc}") from exc
        if not rows:
            raise ValidationError("CSV sans transaction")
        return tuple(rows)
    except (UnicodeError, csv.Error) as exc:
        raise ValidationError(f"CSV illisible : {exc}") from exc

def flag_transactions(rows):
    return tuple(replace(row, flag=row.montant_cents > 500000) for row in rows)

def sum_by(rows, field):
    if field not in ('iban_origine', 'banque_source', 'iban_destinataire'):
        raise ValueError('Agrégation non autorisée')
    result = {}
    for row in rows:
        key = getattr(row, field)
        result[key] = result.get(key, 0) + row.montant_cents
    return dict(sorted(result.items()))

def to_csv(rows):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        record = {k: getattr(row, k) for k in COLUMNS[:-1]}
        record['montant'] = format(Decimal(row.montant_cents)/100, '.2f')
        writer.writerow(record)
    return output.getvalue().encode('utf-8')
