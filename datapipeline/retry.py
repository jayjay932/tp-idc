"""Retry borné ; seuls les incidents temporaires sont réessayés."""
import logging
import time

log = logging.getLogger(__name__)
class TemporaryError(RuntimeError):
    """Incident temporaire injecté pour les démonstrations et tests."""

class Fault:
    def __init__(self, failures=0):
        self.remaining = failures
    def trigger(self):
        if self.remaining > 0:
            self.remaining -= 1
            raise TemporaryError('Incident temporaire simulé')

def retry(operation, *, attempts=4, delay=0.2, transient=lambda exc: isinstance(exc, TemporaryError),
          sleep=time.sleep, label='opération'):
    if attempts < 1 or delay < 0:
        raise ValueError('attempts >= 1 et delay >= 0 requis')
    for number in range(1, attempts+1):
        try:
            return operation()
        except Exception as exc:
            if not transient(exc):
                raise
            log.warning('%s : tentative %s/%s échouée : %s', label, number, attempts, exc)
            if number == attempts:
                log.error('%s : nombre maximal de tentatives atteint', label)
                raise
            wait = min(delay * 2 ** (number-1), 10)
            log.info('Nouvelle tentative dans %.2f s', wait)
            sleep(wait)
