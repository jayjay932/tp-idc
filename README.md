# TP IDC — Pipeline de transactions financières

Projet pédagogique complet pour le sujet « Intégration Déploiement Continu » : génération CSV, validation, transformations pures, base relationnelle, tests CI, reprise sur erreur, stockage S3 local, OCR Tesseract et extraction avec un petit modèle SLM Ollama.

**Commencer par la section 2 pour Windows + Docker.** Aucun compte cloud ni paiement n'est nécessaire pour les niveaux 1 et 2 et les démonstrations OCR/SLM locales. Le niveau 3 couvre uniquement les options 2 (OCR) et 3 (SLM), conformément au choix retenu. Aucun compte cloud, Terraform ou déploiement sur machine virtuelle n’est nécessaire.

## Sommaire

1. Périmètre et état de vérification
2. Premier lancement sur Windows avec Docker
3. Mode Python local, sans Docker
4. Résultats attendus et lecture de la base
5. Explication de chaque fichier
6. Fonctionnement et méthodes utilisées
7. Tests et démonstrations des pannes
8. Git et GitHub Actions
9. Niveau 3 : OCR et SLM
10. Configuration et commandes
11. Dépannage
12. Limites et prochaines vérifications
13. Références

## 1. Périmètre et état de vérification

Le PDF n'impose pas de fournisseur CI ni de SGBD. GitHub Actions est utilisé. SQLite simplifie le premier lancement ; PostgreSQL est utilisé dans la stack Docker locale. Le S3 local est RustFS. Les options 2 (OCR) et 3 (SLM) sont présentes : elles satisfont le minimum de deux améliorations demandé au niveau 3. Les options 1 et 4 ne font pas partie de ce projet.

| Exigence | Implémentation | Comment la démontrer |
|---|---|---|
| N1 : CSV de 5 à 10 transactions | Trois CSV déterministes de six lignes | `generate` ou `demo` |
| N1 : trois sommes, flag > 5000 | Fonctions pures + vues SQL | Tests, `inspect` |
| N1 : base relationnelle et pipeline automatique | SQLite / PostgreSQL, CLI et Compose | Une commande de démarrage |
| N1 : tests d'intégration CI | `unittest`, GitHub Actions | Workflow CI |
| N1 : échec, correction et réussite | Script de scénarios + workflow manuel | Logs fournis ; captures GitHub à effectuer |
| N1 : retry d'insertion et absence de doublons | Transaction atomique + SHA-256 unique | Tests de rollback et de concurrence |
| N2 : démarrage S3, bucket, upload et vérification | Compose RustFS + boto3 | `demo --source s3` |
| N2 : lecture depuis S3 et retry | Lecture des octets en mémoire | Tests Moto et test S3 réel en CI |
| N3 option 2 : OCR | Tesseract → validation → CSV commun | Image exemple fournie |
| N3 option 3 : SLM | Ollama + Qwen 2.5 1.5B → JSON structuré | Modèle à télécharger |

**Vérifications à la livraison :** lire [docs/VALIDATION.md](docs/VALIDATION.md). Les tests exécutés sont distingués des tests conditionnels. Aucune exécution GitHub et aucune inférence réelle Ollama ne sont présentés comme déjà réalisés. Les workflows correspondants sont fournis pour les exécuter avec vos accès. Docker n’est pas disponible dans l’environnement de préparation.

## 2. Premier lancement sur Windows avec Docker

### 2.1 Préparer le dossier

1. Extraire entièrement le ZIP dans un dossier, par exemple `C:\Users\jason\Documents\tp-idc`.
2. Ouvrir **Docker Desktop** et attendre que le moteur soit prêt. Utiliser les conteneurs Linux (WSL2).
3. Ouvrir PowerShell **dans le dossier `tp-idc`**, celui qui contient `compose.yaml` et `README.md`.
4. Vérifier les outils :

```powershell
python --version
docker --version
docker compose version
git --version
```

Python 3.11 ou supérieur est requis pour le mode local. Docker emploie son propre Python 3.12, indépendamment de la version installée sur le PC. Prévoir quelques Go de disque pour les images ; pour le SLM, prévoir aussi le téléchargement du modèle et de la mémoire disponible.

### 2.2 Exécuter la stack complète

```powershell
Copy-Item .env.example .env
docker compose up -d postgres s3
docker compose build pipeline
docker compose run --rm pipeline demo --source s3
docker compose run --rm pipeline inspect
réserver les réglages ultérieurs. Pour automatiser ces commandes :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Le script ne nécessite pas de modifier la politique PowerShell globale. Sous Linux/macOS : `bash scripts/start.sh`.

**Ce qui se passe :** Docker démarre PostgreSQL et RustFS. L'application attend le service PostgreSQL, réessaie la préparation du bucket jusqu'à disponibilité du S3, génère les trois CSV, les téléverse, relit leurs octets pour vérifier l'upload, liste les objets du bucket, récupère leur contenu depuis S3, valide chaque transaction, calcule les flags et insère les lignes et leur marqueur de fichier dans une même transaction SQL. Les agrégations sont consultables dans les vues de la base.

La génération utilise un dossier temporaire propre au conteneur applicatif. La lecture métier du niveau 2 passe par S3, et non par ce dossier. Les données SQL et les objets S3 persistent dans des volumes Docker nommés.

### 2.3 Vérifier le résultat et le rejouement

```powershell
docker compose run --rm pipeline run --source s3
docker compose run --rm pipeline inspect
```

La seconde exécution doit afficher `inserted: 0` et `skipped: 3`. Il doit toujours y avoir **18 transactions**, et non 36.

Console S3 : <http://localhost:9001>, identifiants du `.env` (`S3_ACCESS_KEY` et `S3_SECRET_KEY`). Bucket : `transactions`, préfixe : `incoming/`. L'API S3 écoute sur <http://localhost:9000>. Ces ports sont liés à la boucle locale du PC.

### 2.4 Arrêter ou réinitialiser

```powershell
docker compose down
```

Cela conserve les données. Pour repartir à zéro **en effaçant la base et les objets S3** :

```powershell
docker compose --profile ai down -v
```

Relancer ensuite la section 2.2. Ne pas supprimer les volumes d'un environnement contenant des données à conserver.

## 3. Mode Python local, sans Docker

Le niveau 1 et ses tests métier utilisent uniquement la bibliothèque standard Python. Ce mode permet de démarrer rapidement sans installer PostgreSQL ou S3.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m datapipeline demo
.\.venv\Scripts\python.exe -m datapipeline inspect
.\.venv\Scripts\python.exe -m unittest tests.test_pipeline -v
```

L'activation du venv n'est pas nécessaire si son interpréteur est appelé directement. Cela évite les blocages PowerShell. Dans la suite, `python` désigne cet interpréteur ou celui du venv activé.

Pour les tests S3 simulés et les outils de développement :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Sous Linux/macOS : `python3 -m venv .venv`, puis `.venv/bin/python ...`.

Les fichiers locaux sont écrits dans `data/incoming`, la base dans `data/pipeline.db`. Le dossier `data` est exclu de Git. Le fichier `.env` est chargé par **Docker Compose**, pas automatiquement par le CLI Python. En mode Python, définir les variables PowerShell avec `$env:NOM="valeur"` ou utiliser `--database`.

## 4. Résultats attendus et lecture de la base

Tous les montants des exemples sont en **euros**. La devise est une convention du projet ; le sujet ne prévoit pas de colonne devise.

| Indicateur après la démonstration | Valeur |
|---|---:|
| Fichiers traités | 3 |
| Transactions | 18 |
| Transactions flaguées | 6 |
| Total en centimes | 4 920 003 |
| Total en euros | 49 200,03 € |

Chaque CSV contient les montants `100.00`, `5000.00`, `5000.01`, `99.99`, `6200.00`, `0.01`. Ces valeurs vérifient le seuil strict : **5 000,00 € n'est pas flagué ; 5 000,01 € l'est**. Les dates varient entre fichiers pour que leurs contenus soient différents.

| Agrégation sur les trois fichiers | Résultat en euros |
|---|---:|
| Émis par IBAN FR / Banque A | 33 900,03 |
| Émis par IBAN DE / Banque B | 15 300,00 |
| Reçu par IBAN DE | 30 300,03 |
| Reçu par IBAN GB | 18 900,00 |

`inspect` renvoie les valeurs en centimes pour conserver des entiers exacts. Dans PostgreSQL :

```powershell
docker compose exec postgres psql -U pipeline -d transactions
```

Puis dans `psql` :

```sql
SELECT * FROM processed_files;
SELECT datetime_transaction, montant_cents, flag FROM transactions;
SELECT group_key, total_cents, total_cents / 100.0 AS total_euros FROM sent_by_iban;
SELECT * FROM sent_by_bank;
SELECT * FROM received_by_iban;
\q
```

Adapter le nom d'utilisateur et de base si `.env` a été modifié. PostgreSQL n'a aucun port exposé sur l'hôte ; `docker compose exec` permet de le consulter.

## 5. Explication de chaque fichier

| Fichier ou dossier | Rôle |
|---|---|
| `datapipeline/__init__.py` | Version et identification du paquet Python |
| `datapipeline/__main__.py` | CLI, lecture des options et variables, orchestration, code retour 1 si erreur |
| `datapipeline/domain.py` | Modèle immutable, lecture/validation CSV en mémoire, flags et sommes pures, sérialisation CSV |
| `datapipeline/generator.py` | Trois fichiers de six lignes reproductibles ; pas de tirage aléatoire |
| `datapipeline/database.py` | Connexions SQLite/PostgreSQL, schéma, transactions, déduplication, vues, rapport |
| `datapipeline/storage.py` | Deux sources interchangeables : dossier local et S3 boto3 |
| `datapipeline/pipeline.py` | Enchaînement lecture → hash → validation → flag → insertion |
| `datapipeline/retry.py` | Retry borné, attente exponentielle et injection d'incident temporaire |
| `datapipeline/extraction.py` | Tesseract et client Ollama, validation du résultat avant création du CSV |
| `tests/test_pipeline.py` | Métier, seuil, erreurs, base, rollback, concurrence, PostgreSQL conditionnel |
| `tests/test_s3.py` | S3 simulé Moto, pagination, retry, vrai S3 conditionnel |
| `tests/test_extraction.py` | Validation extraction, contrat Ollama simulé, vrai OCR, vrai SLM conditionnel |
| `tests/__init__.py` | Rend les modules de tests importables |
| `examples/transaction.png` | Image synthétique pour le vrai OCR, une transaction lisible |
| `examples/transaction.txt` | Texte complet pour le SLM : date, fuseau, comptes, pays, banque et montant |
| `scripts/start.ps1`, `scripts/start.sh` | Démarrage Docker Windows ou Linux/macOS |
| `scripts/create_ocr_sample.py` | Régénération de l'image synthétique avec Pillow |
| `scripts/visualize_logs.py` | Produit des visualisations PNG des journaux réellement enregistrés |
| `scripts/demo_failures.py` | Exécute les scénarios de panne et écrit les journaux réels |
| `scripts/check_stack.py` | Vérification des valeurs SQL depuis un environnement Python configuré |
| `Dockerfile` | Image Python avec Tesseract, client S3 et PostgreSQL ; utilisateur non root |
| `compose.yaml` | Services PostgreSQL, RustFS, initialisation permissions, application et Ollama |
| `.env.example` | Paramètres locaux à copier ; aucune clé cloud nécessaire |
| `.gitignore`, `.dockerignore` | Exclusion des secrets, environnements et fichiers générés |
| `requirements.txt` | Dépendances de production, versions majeures bornées |
| `requirements-dev.txt` | Moto, Pillow et parseur YAML pour la vérification |
| `pyproject.toml` | Métadonnées Python et installation possible avec `pip install .` |
| `.github/workflows/ci.yml` | Tests Python 3.11/3.12 et vraie stack Docker locale |
| `.github/workflows/demo-error.yml` | Démonstration manuelle rouge puis verte sur GitHub |
| `.github/workflows/slm.yml` | Test manuel avec vrai modèle Ollama |
| `docs/ARCHITECTURE.md` | Schéma du flux, modèle de données et garanties détaillées |
| `docs/CAPTURES.md` | Scénario de démonstration et captures authentiques à réaliser |
| `docs/VALIDATION.md` | Résultats vérifiés, exclusions et limites de validation |
| `docs/evidence/` | Journaux réellement obtenus et visualisations de ces journaux |

## 6. Fonctionnement et méthodes utilisées

### Séparation des responsabilités

Les sources `LocalSource` et `S3Source` renvoient des octets. La fonction `parse_csv` ne connaît ni le disque ni S3. Les fonctions `flag_transactions` et `sum_by` reçoivent des objets et renvoient de nouveaux résultats, sans modifier leurs entrées. `Transaction` est une dataclass gelée (`frozen=True`). L'orchestration et l'accès à la base sont séparés du métier.

Les trois calculs Python sont vérifiés par des résultats attendus indépendants. En base, les mêmes regroupements sont exposés par trois **vues SQL**, recalculées à la lecture : les agrégats ne deviennent donc pas obsolètes lors de l'ajout de fichiers. Le flag est matérialisé dans chaque ligne. Une contrainte SQL vérifie qu'il correspond bien au montant.

### Validation

Colonnes attendues, dans cet ordre :

```text
datetime_transaction,iban_origine,pays_source,banque_source,iban_destinataire,pays_destinataire,montant
```

CSV UTF-8, séparateur virgule, point décimal. Les sept champs sont obligatoires. Date ISO 8601 avec heure et fuseau, IBAN majuscule de longueur 15 à 34 avec clé modulo 97 valide, pays sur deux lettres cohérent avec le préfixe IBAN, banque non vide, montant strictement positif, fini et à deux décimales au maximum. La validation ne consulte pas de banque réelle et ne contrôle pas l'existence des comptes. Elle n'implémente pas la table de longueurs IBAN propre à chaque pays ni un annuaire ISO exhaustif.

Les montants sont lus avec `Decimal`, puis convertis en **centimes entiers**. Cela évite les erreurs binaires des `float`. Aucun montant invalide n'est arrondi silencieusement.

### Anti-doublons et atomicité

1. Calculer le SHA-256 des octets du fichier.
2. Vérifier `processed_files` pour éviter de retraiter un contenu déjà connu.
3. Valider intégralement le fichier avant toute insertion de ses lignes.
4. Dans une seule transaction SQL, insérer le marqueur de fichier avec `ON CONFLICT DO NOTHING`, puis toutes ses lignes.
5. Commit uniquement si tout réussit ; sinon rollback du marqueur **et** des lignes.

La clé primaire sur le hash bloque deux insertions concurrentes du même fichier. La clé `(content_hash, line_number)` protège également les lignes. Le test concurrent vérifie qu'un seul des quatre appels insère réellement les six transactions.

**Portée de la garantie :** même contenu binaire = ignoré, même s'il est renommé ou provient d'une autre source. Un contenu modifié produit un autre hash. Un changement de formatage ou l'export CSV d'une transaction déjà présente peut donc être considéré comme nouveau. Sans identifiant de transaction métier dans le sujet, le projet garantit la déduplication des fichiers, pas celle de transactions identiques placées dans des fichiers différents. Une correction d'un ancien fichier s'ajoute aux données ; elle ne remplace pas automatiquement les lignes historiques.

Le commit est **par fichier**, pas pour tout le bucket. Si le deuxième fichier est invalide, le premier peut déjà être enregistré. Au lancement suivant, il sera ignoré et le traitement reprendra sans doublon. Un fichier invalide n'est jamais marqué comme réussi.

### Retry et panne simulée

Par défaut : quatre tentatives, pauses de 0,2 s, 0,4 s et 0,8 s. Les pauses sont plafonnées à dix secondes. Les logs indiquent chaque tentative et l'arrêt final ; le CLI retourne 1 si la panne persiste. L'initialisation attend les services avec jusqu'à trente tentatives.

Les erreurs temporaires reconnues sont les verrouillages SQLite, incidents opérationnels PostgreSQL et certaines erreurs réseau/serveur S3. Une erreur de validation ou un refus S3 403 échoue immédiatement. Les erreurs S3 404 à la récupération sont considérées temporairement réessayables puis échouent au maximum prévu.

`--db-failures 2` provoque deux exceptions **après les INSERT mais avant le commit** : cela teste le rollback, et pas seulement un échec avant toute écriture. `--s3-failures 2` échoue au début de deux récupérations d'objet. Le SDK S3 a son retry interne limité à une tentative afin que la politique applicative reste lisible.

### Lecture S3

Le listing S3 est paginé, les clés CSV sont triées, et le contenu est chargé en mémoire. Un test efface les CSV locaux après upload puis traite correctement les objets S3. Un autre crée plus de mille objets pour vérifier la pagination.

## 7. Tests et démonstrations des pannes

### Suite automatique

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Les tests métier couvrent notamment `5000.00`/`5000.01`, l'immuabilité, les trois totaux, les montants invalides, les en-têtes, les IBAN, le stockage réel SQLite, les flags SQL, la déduplication au rejouement et au renommage, le rollback, l'épuisement des retries et les appels concurrents. Moto simule le **protocole S3 côté SDK** ; ce n'est pas une exécution de RustFS. Le job Docker de la CI complète cette couverture avec RustFS et PostgreSQL réels.

Trois tests sont conditionnels : vrai PostgreSQL, vrai S3, vrai SLM. Un test OCR peut aussi être ignoré si Tesseract n'est pas installé. Un résultat `OK (skipped=...)` doit être lu avec ces conditions, pas comme une preuve de toutes les intégrations.

### Échec puis correction en local

```powershell
python scripts/demo_failures.py
```

Le script crée un environnement temporaire isolé, corrompt le montant du premier CSV, observe le code 1 et l'erreur, restaure les octets originaux, observe le succès, rejoue sans doublon, simule deux pannes SQL temporaires, puis un épuisement. Les logs sont conservés dans `docs/evidence`. Il vérifie aussi qu'aucune ligne n'est restée après l'épuisement des tentatives.

Démonstration Docker d'un retry base et S3 : partir d'une stack vide si les fichiers ont déjà été traités. Sinon le retry d'insertion ne sera pas déclenché, puisque les fichiers seront correctement ignorés.

```powershell
docker compose run --rm pipeline demo --source s3 --db-failures 2 --s3-failures 2
```

Le générateur reproduit les mêmes données volontairement : relancer `demo` sur une base déjà remplie teste le rejouement plutôt qu'un nouvel import.

Pour un arrêt persistant de lecture S3 :

```powershell
docker compose run --rm pipeline run --source s3 --s3-failures 9 --attempts 3 --delay 0.2
```

Cette commande doit retourner un code d'échec. Les logs des services : `docker compose logs --no-color`. Pour le niveau 1, les journaux et visualisations fournis facilitent la lecture ; **les captures d'écran GitHub authentiques sont à effectuer lors de l'exécution sur votre dépôt**, selon [docs/CAPTURES.md](docs/CAPTURES.md).

## 8. Git et GitHub Actions

Créer un dépôt GitHub vide, par exemple `tp-idc`. Ne pas committer `.env`, `.venv` ou `data`.

```powershell
git init
git add .
git commit -m "Pipeline data CI avec OCR et SLM locaux"
git branch -M main
git remote add origin https://github.com/TON-COMPTE/tp-idc.git
git push -u origin main
```

Remplacer l'URL par celle de ton dépôt. La première authentification dépend de Git Credential Manager ou de ta configuration SSH ; aucun mot de passe GitHub n'est inclus dans le projet.

Dans **Actions**, le workflow CI s'exécute sur push et pull request :

- job `python` : tests Python 3.11 et 3.12, vrai OCR et scénarios de panne ;
- job `docker` : démarrage RustFS/PostgreSQL, retry, pipeline, rejouement, vérification exacte des résultats, base PostgreSQL de test séparée, vrai S3 et OCR conteneur ;

Les journaux sont téléchargeables dans les artifacts du workflow. Les tests peuvent échouer en cas de téléchargement d'image indisponible ou d'évolution des services : consulter d'abord les logs. Il n'est pas nécessaire de créer de secrets pour la CI standard ; elle utilise les valeurs locales de démonstration.

Pour montrer un workflow réellement rouge : **Actions → Démonstration échec puis correction → Run workflow → `invalid`**. Recommencer avec `corrected`. Le premier échoue volontairement ; ce n'est pas un bug caché du projet. Le workflow doit être présent sur la branche par défaut pour être proposé dans l'interface.

Le test SLM réel est un workflow manuel distinct afin de ne pas retélécharger un modèle pour chaque commit.

## 9. Niveau 3 : OCR et SLM

### OCR Tesseract

L'image exemple est synthétique, sans donnée bancaire personnelle. Le format d'image supporté par cette démonstration est explicite : **une transaction par ligne, sept champs dans l'ordre CSV, séparés par `|`, sans en-tête**. Il ne s'agit pas d'un parseur universel de tous les relevés bancaires.

Dans Docker (Tesseract est déjà installé) :

```powershell
New-Item -ItemType Directory -Force data\extracted
# La sortie est montée dans le dossier du PC pour survivre à --rm.
docker compose run --rm -v "${PWD}/data/extracted:/app/data/extracted" pipeline ocr --input examples/transaction.png --output data/extracted/ocr.csv
```

Sous Linux/macOS, remplacer le montage par `-v "$PWD/data/extracted:/app/data/extracted"`. Sous Windows, utiliser Docker Desktop avec l'accès au disque du projet autorisé.

Pour rejoindre exactement le flux S3 → traitement → base :

```powershell
docker compose run --rm -v "${PWD}/data/extracted:/app/data/extracted" pipeline upload --directory data/extracted
docker compose run --rm pipeline run --source s3
docker compose run --rm pipeline inspect
```

Après l'OCR, l'ajout d'un fichier contenant une transaction de 6 200 € fait passer la base de démonstration à 19 transactions, 7 flags et 55 400,03 €. Les assertions de la démo à 18 lignes ne s'appliquent donc plus après ces ajouts.

Tesseract peut introduire des espaces dans les champs techniques : l'extraction supprime uniquement ces espaces. Elle ne remplace pas un `O` par un `0` et ne devine pas de valeur manquante. Toute sortie invalide est rejetée avant ingestion. La valeur peut néanmoins être mal lue tout en restant valide ; une vérification humaine reste adaptée à des documents réels.

En Python natif, installer Tesseract et ses données `eng` sur le PC, l'ajouter au PATH, puis :

```powershell
python -m datapipeline ocr --input examples/transaction.png --output data/extracted/ocr.csv
```

### SLM Ollama + Qwen 2.5 1.5B

Ollama exécute localement un petit modèle ; aucune clé API payante n'est nécessaire. Le téléchargement initial requiert Internet. Un CPU fonctionne, avec une latence variable ; prévoir plusieurs Go de RAM disponibles. Le choix est configurable par `SLM_MODEL`.

```powershell
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:1.5b
docker compose run --rm -v "${PWD}/data/extracted:/app/data/extracted" pipeline slm --input examples/transaction.txt --output data/extracted/slm.csv
```

L'application appelle `POST /api/generate`, envoie un schéma JSON, désactive le streaming et fixe la température à zéro. La sortie est validée avec **les mêmes règles que les CSV**. Les champs manquants doivent rester vides et être rejetés. Le texte exemple inclut volontairement l'année, l'heure, le fuseau et la banque : ces éléments ne sont pas inventés par l'application.

Le modèle reste probabiliste. Un schéma JSON garantit une structure, pas l'exactitude factuelle. Pour le tester réellement : lancer le workflow **Test SLM réel (manuel)** ou définir en local :


```powershell
$env:TEST_OLLAMA_URL="http://localhost:11434"
$env:SLM_MODEL="qwen2.5:1.5b"
python -m unittest tests.test_extraction.ExtractionTests.test_real_slm -v
```

Pour ingérer le CSV SLM : mêmes commandes `upload` puis `run --source s3` que pour l'OCR. Attention : si l'OCR et le SLM produisent des fichiers aux octets strictement identiques, le second est ignoré. Des octets différents pour une même transaction ne bénéficient pas d'une déduplication métier automatique.

## 10. Configuration et commandes

| Paramètre | Valeur par défaut / rôle |
|---|---|
| `DATABASE_URL` | CLI : `sqlite:///data/pipeline.db` ; Compose : PostgreSQL interne |
| `S3_ENDPOINT` | CLI : `http://localhost:9000` ; Compose : `http://s3:9000` |
| `S3_BUCKET` | `transactions` |
| `S3_PREFIX` | `incoming/`, uniquement pour le CLI ; injecter avec `-e` si personnalisé dans Compose |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Identifiants locaux, partagés par RustFS et l'application |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Paramètres Compose PostgreSQL |
| `RUSTFS_IMAGE` | `rustfs/rustfs:1.0.0`, remplaçable après vérification du tag |
| `OLLAMA_URL` | CLI : `http://localhost:11434` ; Compose : `http://ollama:11434` |
| `SLM_MODEL` | `qwen2.5:1.5b` |
| `TEST_POSTGRES_URL` | Active un test qui vide les tables de la base indiquée : base de test uniquement |
| `TEST_S3_ENDPOINT` | Active le test S3 réel, bucket `ci-integration` |
| `TEST_OLLAMA_URL` | Active l'inférence réelle du SLM |

Les mots de passe contenant `@`, `:`, `/`, `%` doivent être encodés dans une URL PostgreSQL. Pour le TP, choisir des valeurs longues composées de lettres, chiffres, tirets et underscores afin de simplifier la configuration.

| Commande CLI | Effet |
|---|---|
| `generate` | Générer trois CSV dans `--directory` |
| `demo` | Générer, uploader si S3, traiter et afficher le rapport |
| `run` | Traiter les CSV existants de la source choisie |
| `inspect` | Initialiser si nécessaire et afficher l'état de la base |
| `upload` | Envoyer tous les CSV de `--directory` dans S3 avec relecture de contrôle |
| `ocr --input ... --output ...` | Extraire une image et écrire un CSV validé |
| `slm --input ... --output ...` | Extraire un texte via Ollama et écrire un CSV validé |
| `watch --source s3 --interval 60` | Exécuter le traitement périodique |

Options générales : `--database`, `--directory`, `--source local|s3`, `--db-failures`, `--s3-failures`, `--attempts`, `--delay`. Aide : `python -m datapipeline --help`. Les options sans rapport avec une commande n'ont pas d'effet (par exemple `--input` pour `inspect`).

## 11. Dépannage

| Symptôme | Vérification / action |
|---|---|
| `docker` non reconnu ou moteur inaccessible | Lancer Docker Desktop et vérifier `docker info` |
| Compose ne trouve pas de configuration | Se placer dans le dossier contenant `compose.yaml` |
| `No module named datapipeline` | Même dossier ; utiliser `python -m datapipeline`, ou installer avec `pip install .` |
| Port 9000/9001/11434 occupé | Arrêter le service concurrent ou modifier le port hôte ; garder le port interne inchangé |
| RustFS refuse l'accès au volume | Vérifier `docker compose logs s3-permissions s3` ; l'init doit terminer avec succès |
| Image introuvable / téléchargement impossible | Vérifier Internet, proxy, tag et accès Docker Hub ; `docker compose pull` |
| Erreur certificat en entreprise | Configurer les certificats/proxy de confiance du système et de Docker, puis réessayer |
| S3 connection refused au démarrage | Attendre les retries et vérifier `docker compose logs s3` |
| S3 AccessDenied | Même clé et secret dans RustFS et l'application ; recréer les services après modification |
| PostgreSQL refuse le nouveau mot de passe | Les identifiants init ne modifient pas un volume déjà initialisé ; modifier le rôle SQL ou réinitialiser seulement une stack jetable |
| `inserted: 0`, `skipped: 3` | Résultat normal : ces trois contenus ont déjà été traités |
| Test OCR ignoré | Installer Tesseract, ou utiliser l'image Docker fournie |
| OCR : validation échouée | Relire l'image, améliorer sa lisibilité ; ne pas inventer les champs illisibles |
| Ollama `model not found` | Exécuter `ollama pull` pour la valeur de `SLM_MODEL` |
| SLM dépasse le délai | Vérifier RAM/CPU et disponibilité du modèle ; délai HTTP fixé à 300 s |
| Actions non visibles | Vérifier le dépôt GitHub, l'activation d'Actions et les workflows sur la branche par défaut |

## 12. Limites et prochaines vérifications

Le projet vise une démonstration pédagogique complète. Il ne certifie pas des opérations financières réelles. Fichiers chargés entièrement en mémoire, pas de migration de schéma versionnée, pas de quarantaine des CSV invalides, pas de remplacement automatique des anciennes versions, pas de haute disponibilité sur un poste unique. Les volumes demandent une stratégie de sauvegarde pour une utilisation durable. Les dépendances Python sont bornées par versions majeures mais pas figées transitivement dans un lockfile ; les images sont taguées mais pas verrouillées par digest.

Pour finaliser le rendu : lancer la stack sur le PC, pousser le dépôt, vérifier la CI, exécuter la démonstration rouge puis verte et conserver les captures authentiques. Pour démontrer les deux options retenues du niveau 3, exécuter l’OCR puis le SLM réel et ingérer leurs CSV dans le flux S3 local. Les scripts sont prêts, mais ces résultats dépendent de vos ressources et accès.

## 13. Références

- Sujet fourni : `TP_IDC (1).pdf` (non recopié dans le ZIP).
- RustFS Docker : <https://docs.rustfs.com/en/installation/container/docker>
- Boto3 S3 : <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html>
- Psycopg transactions : <https://www.psycopg.org/psycopg3/docs/basic/transactions.html>
- GitHub Actions : <https://docs.github.com/en/actions>
- Ollama API generate : <https://docs.ollama.com/api/generate>
- Tesseract : <https://tesseract-ocr.github.io/>
