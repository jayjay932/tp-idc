# Captures et démonstration au professeur

Les fichiers `.log` de `evidence/` contiennent des exécutions réelles de préparation. Les PNG sont des **visualisations des sorties enregistrées**, pas des captures d'écran de GitHub Actions. Ils ne doivent pas être présentés comme la preuve d'un workflow GitHub déjà exécuté.

## Scénario exigé au niveau 1

1. **Cause** : remplacement du premier montant `100.00` par `invalide` dans `transactions_01.csv`.
2. **Échec** : le CSV est rejeté par `validate_record`, le CLI affiche `PIPELINE EN ÉCHEC` et retourne le code 1.
3. **Erreur** : `ValidationError` avec le numéro de ligne et le message sur le montant positif à deux décimales.
4. **Correction** : restauration des octets initiaux du fichier généré.
5. **Réussite** : 3 fichiers, 18 transactions, 6 flags, total 4 920 003 centimes.

`python scripts/demo_failures.py` exécute ces cinq étapes, puis le rejouement et les retries, dans des dossiers temporaires afin de ne pas modifier votre base habituelle. Il conserve ses résultats dans `evidence/`.

## Captures GitHub authentiques à produire

Après push du dépôt sur `main` :

| Capture | Action à effectuer | Information visible |
|---|---|---|
| 1 — cause | Ouvrir `demo-error.yml`, étape d'injection | Remplacement du montant |
| 2 — échec | Lancer le workflow avec `scenario=invalid` | Workflow rouge et étape de traitement échouée |
| 3 — message | Déplier l'étape en erreur | Montant invalide, ligne CSV et code de sortie |
| 4 — correction | Relancer avec `scenario=corrected` | Paramètre corrigé ; absence de corruption |
| 5 — réussite | Déplier la sortie de la nouvelle exécution | Workflow vert et totaux attendus |
| 6 — CI intégration | Ouvrir la CI standard | Jobs Python et Docker réussis |
| 7 — retry | Déplier la première démo du job Docker | Tentatives S3/SQL, puis insertion réussie |
| 8 — anti-doublons | Déplier le second traitement du job Docker | 0 insertion, 3 fichiers ignorés |

Sous Windows : `Win + Maj + S`, sélectionner la zone, enregistrer le PNG dans un sous-dossier de rendu. Ajouter éventuellement une brève légende au rapport. Ne pas capturer de secrets ou de clés SSH.
