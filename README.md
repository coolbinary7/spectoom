# Spectoom 2.2.1

Spectoom est un outil interne gratuit de génération et de préparation de médias musicaux. La connexion sert uniquement à séparer les utilisateurs et à conserver leurs projets, médias importés, rendus et conversions.

## Modules

### Entrées en playlist

- MP4 vertical 1080 × 1350, ratio 4:5, durée exacte de 20 secondes.
- Une à six playlists.
- Logos DSP en noir, blanc ou contraste automatique.
- Sélection audio fixe de 20 secondes avec lecture automatique.
- Aperçu et rendu issus du même moteur de composition.

### Nouvelle sortie

- Single, EP ou album.
- Templates Portrait éditorial et Artwork central.
- Libellé supérieur fixe `new`.
- Branding Virgin Music Afrique.
- MP4 vertical 1080 × 1350 de 20 secondes.

### Spectrum YouTube

- MP4 horizontal 1920 × 1080 sur toute la durée du morceau.
- Six styles : Barres, Miroir, Fluide, Colline, LED et Particules.
- Fond image ou vidéo, cover, titres, police, palette et sensibilité.
- Logo entièrement facultatif. Aucun logo Spectoom n'est incrusté par défaut.
- La prévisualisation et le MP4 utilisent la même visualisation calculée depuis l'audio.

### Conversion

Spectoom accepte les fichiers audio reconnus par le moteur FFmpeg installé et les convertit en :

- WAV PCM ;
- 44,1 kHz ;
- 16 bits ;
- stéréo.

Les vidéos sont traitées de la même manière après extraction de leur première piste audio.

Les covers sont converties en TIFF :

- 3000 × 3000 pixels ;
- 300 DPI ;
- RVB, 8 bits par canal, trois canaux ;
- sans transparence ;
- compression LZW ;
- sans profil ICC ni balise TIFF 34675.

**Règle de téléchargement :**

- un seul fichier envoyé produit un seul fichier téléchargeable directement (`.wav` ou `.tiff`) ;
- plusieurs fichiers envoyés produisent une archive ZIP contenant les résultats et un rapport.

## Nouveautés 2.2.1

- Correction du téléchargement des conversions dont le nom contient des espaces, des accents ou des caractères encodés.
- Les conversions unitaires sont téléchargées directement en `.tiff` ou `.wav`, sans réponse JSON parasite.
- Les conversions déjà terminées en V2.2.0 redeviennent téléchargeables après la mise à jour, sans nouvelle conversion.
- ZIP réservé aux lots de plusieurs fichiers.
- Prise en charge de tout audio que FFmpeg peut décoder, avec sortie WAV 44,1 kHz, 16 bits et stéréo.
- Les correctifs V2.2.0 du formulaire de création, du logo Spectrum facultatif et des six styles Spectrum restent inclus.

## Installation Windows

### Installation complète

1. Décompresser `spectoom-v2.2.1-complet.zip`.
2. Ouvrir le dossier `spectoom`.
3. Double-cliquer sur `run.bat`.
4. Laisser le premier démarrage installer les dépendances Python.
5. Ouvrir `http://127.0.0.1:8080` si le navigateur ne s'ouvre pas automatiquement.

### Mise à jour depuis Spectoom 2.0 ou 2.1

1. Fermer Spectoom et toutes les fenêtres noires qui exécutent `server.py`.
2. Décompresser `spectoom-v2.2.1-correctif-conversion.zip`.
3. Ouvrir `spectoom-update-2.2.1`.
4. Double-cliquer sur `UPDATE_SPECTOOM_V2.2.1.bat`.
5. Sélectionner, si nécessaire, le dossier qui contient directement `server.py`, `static`, `data` et `run.bat`.

L'installateur sauvegarde `data/store.json` puis conserve les projets, uploads, polices, MP4 et conversions.

## Installation macOS / Linux

```bash
python3 -m pip install -r requirements.txt
./run.sh
```

## Comptes

Configurer les six variables SPECTOOM_USER_* et SPECTOOM_ADMIN_* dans l’environnement avant le lancement, y compris en local. Aucun mot de passe par défaut. `.env.example` est un modèle vide ; Python ne charge pas automatiquement `.env`.

## Vérification

Ouvrir :

```text
http://127.0.0.1:8080/api/health
```

Le résultat doit notamment contenir :

```json
{
  "ok": true,
  "service": "Spectoom",
  "version": "2.2.1"
}
```

## Dépendances

- Python 3.10 ou plus récent recommandé ;
- Pillow ;
- Mutagen ;
- imageio-ffmpeg ;
- FFmpeg système facultatif mais recommandé pour prendre en charge le plus grand nombre de formats.

## Arborescence utile

```text
spectoom/
├── server.py
├── run.bat
├── run.sh
├── static/
├── data/
│   ├── store.json
│   ├── uploads/
│   ├── renders/
│   ├── conversions/
│   ├── fonts/
│   └── backups/
└── docs/
```

## Limites connues

- « Tout fichier audio » signifie tout format que la version locale de FFmpeg sait décoder. Un format chiffré, protégé par DRM ou corrompu ne peut pas être converti.
- L'édition complète est conçue en priorité pour ordinateur de bureau.
- Le rendu Spectrum peut être long puisqu'il suit la durée complète du morceau.
- L'installateur PowerShell a été inspecté et simulé dans l'environnement de livraison, mais n'a pas été exécuté dans une session Windows réelle.

---

## Déploiement cloud GitHub + Render

Cette archive contient une variante cloud durcie. Le guide complet est disponible dans `DEPLOIEMENT_GITHUB_RENDER.md`.
