# État de validation à la livraison

Vérifications réalisées le 8 novembre 2026 sur Python 3.12.14, Linux.

| Contrôle | Résultat observé |
|---|---|
| Tests automatiques | 30 découverts, 27 réussis, 3 ignorés conditionnellement, aucun échec |
| Métier, base SQLite et concurrence | Réussis avec vérification de valeurs attendues indépendantes |
| Retry SQL et épuisement | Réussis, y compris rollback après écritures avant commit |
| S3 via Moto | Réussi, upload/relecture, pagination >1000 clés, retry et épuisement |
| OCR Tesseract réel | Image fournie extraite, validée et ingérée : 1 transaction de 6200 €, flag actif |
| SLM | Contrat HTTP/JSON simulé testé ; inférence réelle non exécutée |
| Scénarios d'échec | Six journaux produits avec codes retour conformes aux attentes |
| Python | Compilation de tous les modules et scripts réussie |
| YAML | Compose et les trois workflows analysés sans erreur de syntaxe |
| Shell | `bash -n` réussi pour le script de démarrage shell |
| PostgreSQL / RustFS réels | Non exécutés ici : moteur Docker absent ; tests prévus dans le job Docker de la CI |
| GitHub Actions | Workflows fournis, aucune exécution sur un dépôt utilisateur dans cette session |

Les trois tests conditionnels ignorés sont le PostgreSQL réel, le S3 réel et le SLM réel. L'OCR réel a bien été exécuté. Le test Ollama simulé valide le contrat applicatif ; il ne mesure pas la qualité d'un modèle.

Les journaux se trouvent dans `evidence/`. Les PNG montrent les sorties des journaux réellement obtenus, avec un en-tête qui les distingue d'une capture GitHub. Les captures authentiques demandées par le sujet restent à effectuer avec le dépôt de l'étudiant : voir `CAPTURES.md`.

Les dépendances Python utilisent des plages de versions majeures. Les images sont épinglées à des tags, non à des digests. La validation finale de ces téléchargements et de la stack sur le PC et GitHub est nécessaire. Si un service évolue ou si un téléchargement est indisponible, le README donne les points de diagnostic.

Périmètre révisé : niveaux 1 et 2, puis options 2 (OCR) et 3 (SLM) du niveau 3. Les fichiers de déploiement distant et d’infrastructure ont été retirés.
