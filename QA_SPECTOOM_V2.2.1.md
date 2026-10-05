# Rapport de vérification — Spectoom 2.2.1

## Périmètre

Correctif du téléchargement des résultats de conversion. Le moteur de rendu vidéo et la structure des projets restent inchangés.

## Cause reproduite en V2.2.0

Une conversion unitaire portant le nom `COVER BAD OUZI.png` produisait correctement `COVER BAD OUZI.tiff`. Le navigateur demandait ensuite :

```text
/media/conversions/COVER%20BAD%20OUZI.tiff?download=1
```

Le serveur comparait le segment encodé `COVER%20BAD%20OUZI.tiff` au nom enregistré `COVER BAD OUZI.tiff`, répondait HTTP 404 en JSON, puis le navigateur proposait un téléchargement `.json` indisponible.

## Correctifs contrôlés

- Décodage percent-encoding avant recherche du fichier.
- Rejet des chemins comportant des séparateurs après décodage.
- URLs de sortie encodées pour les nouveaux jobs.
- `Content-Disposition` avec `filename*` UTF-8 et nom ASCII de secours.
- Version serveur, frontend et lanceurs : `2.2.1`.
- Renderer inchangé : `v2.2.0-shared-spectrum`.

## Tests exécutés

### Validation statique

- `python3 -m py_compile server.py` : réussi.
- `node --check static/app.js` : réussi.
- Cohérence des versions `server.py`, `app.js`, `index.html`, `run.bat`, `run.sh` et `open_when_ready.ps1` : réussie.

### Conversion image unitaire

Entrée : `COVER BAD OUZI épreuve.png`.

Résultat :

- HTTP 200 au téléchargement ;
- MIME `image/tiff` ;
- nom UTF-8 transmis dans `Content-Disposition` ;
- TIFF 3000 × 3000 ;
- RGB, 3 canaux, 8 bits par canal ;
- 300 DPI ;
- compression LZW ;
- balise ICC 34675 absente.

### Conversion audio unitaire

Entrée : `Ouzi - B.A.D.wav`.

Résultat :

- HTTP 200 au téléchargement ;
- MIME `audio/x-wav` ;
- WAV PCM 44 100 Hz ;
- 16 bits ;
- stéréo ;
- téléchargement direct, sans ZIP ni JSON.

### Lot de deux fichiers

Entrées : une image et un audio.

Résultat :

- package `zip` ;
- archive téléchargeable en HTTP 200 ;
- TIFF, WAV et `rapport_conversion.txt` présents.

### Compatibilité des anciens résultats

Le serveur accepte les chemins percent-encodés correspondant aux noms avec espaces créés en V2.2.0. La mise à jour ne supprime ni `data/conversions`, ni les enregistrements de l’historique.

## Limite de validation

L’installateur PowerShell a été inspecté et simulé sur une copie de l’application dans l’environnement de livraison. Il n’a pas été exécuté dans une session Windows réelle.
