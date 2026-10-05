# QA — Spectoom 2.2.2 Cloud / GitHub + Render

Date : 5 octobre 2026

## Périmètre vérifié

- variante cloud du package Spectoom 2.2.1 ;
- stockage configurable hors du code via `SPECTOOM_DATA_DIR` ;
- comptes de production configurés par variables d'environnement ;
- absence de comptes de démonstration dans une installation cloud neuve ;
- cookie de session configurable et sécurisé en production ;
- Dockerfile avec FFmpeg, FFprobe et polices système ;
- Blueprint Render avec disque persistant ;
- workflow GitHub Actions de contrôle ;
- rendu MP4 et conversions dans un répertoire de données externe.

## Contrôles réussis

### Syntaxe

- `python -m py_compile server.py reset_demo.py` : OK
- `node --check static/app.js` : OK

### Démarrage cloud

Démarrage avec :

- `SPECTOOM_ENV=production`
- données dans un dossier temporaire externe ;
- comptes utilisateur et administrateur fournis par variables d'environnement ;
- aucun projet de démonstration lorsque `SPECTOOM_SEED_DEMO=0`.

L'endpoint `/api/health` a répondu :

- service `Spectoom` ;
- version `2.2.2-cloud` ;
- FFmpeg disponible ;
- FFprobe disponible ;
- stockage accessible en écriture.

Connexion réelle du compte interne : OK.

### Rendu vidéo réel

Un projet « Entrées en playlist » de démonstration a été rendu en utilisant le répertoire de données cloud externe.

Contrôle FFprobe :

- conteneur MP4 ;
- vidéo H.264 ;
- 1080 × 1350 ;
- 30 images/s ;
- audio AAC ;
- 48 kHz ;
- stéréo ;
- durée 20,000000 secondes.

### Conversion réelle

Une image nommée `COVER ÉTÉ TEST.png` a produit un téléchargement direct `COVER ÉTÉ TEST.tiff` :

- 3000 × 3000 ;
- RGB ;
- 300 DPI ;
- compression TIFF LZW ;
- aucune balise ICC 34675.

Un fichier FLAC mono 48 kHz nommé `Son été test.flac` a produit un téléchargement direct WAV :

- PCM signed 16 bits little-endian ;
- 44 100 Hz ;
- stéréo.

Les noms comportant espaces et accents ont été conservés.

## Sécurité de déploiement ajoutée

- aucun identifiant de production dans le dépôt ;
- mots de passe cloud exigés à 12 caractères minimum avec lettre et chiffre ;
- désactivation automatique des comptes de démonstration connus lors d'une migration vers le cloud ;
- cookie `HttpOnly`, `SameSite=Lax` et `Secure` en production ;
- limitation en mémoire des tentatives de connexion ;
- en-têtes `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` et `Permissions-Policy` ;
- dossier `data` exclu de Git ;
- stockage persistant séparé du code.

## Limites de validation

- Le moteur Docker n'est pas installé dans l'environnement de test : la commande `docker build` n'a pas pu être exécutée ici. Le Dockerfile a été inspecté et le même code a été exécuté directement avec ses dépendances Linux et FFmpeg.
- Aucun compte GitHub ou Render de l'utilisateur n'était connecté : le dépôt distant et le service Render n'ont pas encore été créés.
- Un redéploiement interrompt un rendu en cours, car cette première version cloud conserve le moteur de rendu dans le même processus et utilise un disque mono-instance.
- `store.json` et le stockage local persistant sont adaptés à un petit outil interne. Une utilisation à plus grande échelle nécessitera une base de données et un stockage objet.
