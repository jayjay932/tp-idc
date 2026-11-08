"""SQLite / PostgreSQL : données et marqueur de fichier dans une même transaction."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .retry import retry, TemporaryError

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS processed_files (
        content_hash TEXT PRIMARY KEY, source_name TEXT NOT NULL,
        row_count INTEGER NOT NULL CHECK (row_count > 0),
        processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS transactions (
        content_hash TEXT NOT NULL REFERENCES processed_files(content_hash),
        line_number INTEGER NOT NULL,
        datetime_transaction TEXT NOT NULL,
        iban_origine TEXT NOT NULL, pays_source TEXT NOT NULL, banque_source TEXT NOT NULL,
        iban_destinataire TEXT NOT NULL, pays_destinataire TEXT NOT NULL,
        montant_cents BIGINT NOT NULL CHECK (montant_cents > 0),
        flag INTEGER NOT NULL CHECK (flag IN (0,1)),
        PRIMARY KEY(content_hash, line_number),
        CHECK (flag = CASE WHEN montant_cents > 500000 THEN 1 ELSE 0 END))""",
]
for view, field in [('sent_by_iban','iban_origine'), ('sent_by_bank','banque_source'),
                    ('received_by_iban','iban_destinataire')]:
    SCHEMA.append(f'CREATE VIEW IF NOT EXISTS {view} AS SELECT {field} AS group_key, '
                  f'SUM(montant_cents) AS total_cents FROM transactions GROUP BY {field}')

def schema_statements(postgres=False):
    """PostgreSQL emploie CREATE OR REPLACE VIEW, SQLite IF NOT EXISTS."""
    return tuple(statement.replace('CREATE VIEW IF NOT EXISTS', 'CREATE OR REPLACE VIEW')
                 if postgres else statement for statement in SCHEMA)

class Database:
    def __init__(self, url):
        self.url = url
        self.postgres = url.startswith(('postgresql://', 'postgres://'))
        if not self.postgres and not url.startswith('sqlite:///'):
            raise ValueError('DATABASE_URL doit commencer par sqlite:/// ou postgresql://')

    @contextmanager
    def connect(self):
        if self.postgres:
            import psycopg
            connection = psycopg.connect(self.url, connect_timeout=5)
        else:
            path = self.url.removeprefix('sqlite:///')
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(path, timeout=1)
            connection.execute('PRAGMA foreign_keys = ON')
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute(self, connection, sql, params=()):
        return connection.execute(sql.replace('?', '%s') if self.postgres else sql, params)

    def transient(self, exc):
        if isinstance(exc, TemporaryError):
            return True
        if isinstance(exc, sqlite3.OperationalError):
            return 'locked' in str(exc).lower() or 'busy' in str(exc).lower()
        if self.postgres:
            import psycopg
            return isinstance(exc, (psycopg.OperationalError, psycopg.errors.SerializationFailure,
                                    psycopg.errors.DeadlockDetected))
        return False

    def initialize(self):
        def create():
            with self.connect() as conn:
                for statement in schema_statements(self.postgres):
                    self.execute(conn, statement)
        retry(create, attempts=30, delay=0.2, transient=self.transient, label='initialisation base')

    def seen(self, digest):
        with self.connect() as conn:
            return self.execute(conn, 'SELECT 1 FROM processed_files WHERE content_hash=?', (digest,)).fetchone() is not None

    def insert_file(self, digest, source, rows, fault=None, attempts=4, delay=0.2):
        def insert():
            with self.connect() as conn:
                cursor = self.execute(conn, 'INSERT INTO processed_files(content_hash,source_name,row_count) '
                                      'VALUES(?,?,?) ON CONFLICT(content_hash) DO NOTHING', (digest, source, len(rows)))
                if cursor.rowcount == 0:
                    return False
                for number, row in enumerate(rows, 2):
                    self.execute(conn, 'INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?)',
                                 (digest, number, row.datetime_transaction, row.iban_origine,
                                  row.pays_source, row.banque_source, row.iban_destinataire,
                                  row.pays_destinataire, row.montant_cents, int(row.flag)))
                # Injection APRÈS les écritures mais AVANT commit : teste réellement le rollback.
                if fault:
                    fault.trigger()
            return True
        return retry(insert, attempts=attempts, delay=delay, transient=self.transient, label='insertion base')

    def report(self):
        with self.connect() as conn:
            result = {key: int(self.execute(conn, sql).fetchone()[0]) for key, sql in {
                'files': 'SELECT COUNT(*) FROM processed_files',
                'transactions': 'SELECT COUNT(*) FROM transactions',
                'flagged': 'SELECT COUNT(*) FROM transactions WHERE flag=1',
                'total_cents': 'SELECT COALESCE(SUM(montant_cents),0) FROM transactions'}.items()}
            for view in ('sent_by_iban','sent_by_bank','received_by_iban'):
                # PostgreSQL SUM(BIGINT) retourne Decimal : conserver des centimes entiers.
                result[view] = {key: int(total) for key, total in self.execute(
                    conn, f'SELECT group_key,total_cents FROM {view} ORDER BY group_key').fetchall()}
            return result
