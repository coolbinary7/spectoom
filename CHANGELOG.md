# Changelog Spectoom

## 2.2.1 — 5 octobre 2026

### Conversion et téléchargement

- Correction du décodage des noms de fichiers dans les URLs `/media/conversions/`.
- Les espaces, accents et caractères spéciaux ne provoquent plus de réponse JSON 404.
- Ajout d'URLs de téléchargement percent-encodées pour les nouveaux résultats.
- En-tête `Content-Disposition` compatible UTF-8 avec nom ASCII de secours.
- Les fichiers déjà convertis en V2.2.0 restent récupérables après mise à jour.
- Une conversion unitaire télécharge directement le TIFF ou le WAV ; un lot de plusieurs fichiers produit un ZIP.

### Technique

- Version de l'application : `2.2.1`.
- Renderer inchangé : `v2.2.0-shared-spectrum`.
- Aucun changement de structure des projets ni du dossier `data`.

## 2.2.0 — 5 octobre 2026

### Création de projets

- Réparation du formulaire général « Nouveau projet ».
- Aucune carte sélectionnée ni coche trompeuse à l’ouverture.
- Validation du choix avant activation du bouton de création.
- Création réelle par l’API, puis ouverture immédiate de l’éditeur correspondant.

### Spectrum YouTube

- Logo facultatif et désactivé par défaut.
- Aucun logo Spectoom ajouté automatiquement au MP4.
- Catalogue réduit à Barres, Miroir, Fluide, Colline, LED et Particules.
- Migration automatique des anciens styles supprimés vers Barres.
- Mise en page du parcours Spectrum stabilisée.

### Conversion

- Téléchargement direct pour une conversion unitaire.
- ZIP réservé aux lots de deux fichiers ou plus.
- Tous les fichiers audio reconnus par FFmpeg peuvent être tentés.
- Sortie audio normalisée en WAV PCM 44,1 kHz, 16 bits, stéréo.

### Technique

- Version du renderer : `v2.2.0-shared-spectrum`.
- Détection média par contenu, MIME, FFprobe, Mutagen et FFmpeg.
- Migration des projets historiques sans suppression des données.

## 2.1.0 — 2 octobre 2026

### Export et suivi

- Barre de progression persistante lorsqu’une fenêtre d’export est masquée.
- Suivi global disponible pendant la navigation entre les pages.
- Réouverture du détail, téléchargement direct et état d’échec explicite.

### Création de projets

- Parcours de création réellement branché à l’API.
- Création contextuelle depuis chaque module sans demander de nouveau le type de vidéo.
- Création générique depuis « Nouveau projet » avec choix entre les trois générateurs.

### Polices et branding

- Bibliothèque de polices dans l’onglet Branding.
- Import de polices TTF et OTF avec validation.
- Sélection indépendante de la police dans chaque projet.
- Utilisation de la même police dans l’aperçu et le rendu.

### Nouvelle sortie

- Suppression du réglage de couleur d’accent.
- Suppression du texte « Nouvelle sortie » dans la vidéo.
- Libellé supérieur fixé à « new ».
- Sélecteur de police ajouté.

### Spectrum YouTube

- Aperçu et MP4 fondés sur la même séquence de visualisation générée depuis l’audio.
- Suppression du nom technique du style dans la vidéo.
- Suppression de la mention « Spectoom YouTube ».
- Contrôle des neuf styles avec le nouveau moteur partagé.

### Conversion

- Nouvel onglet Conversion.
- Covers vers TIFF 3000 × 3000, 300 DPI, RGB 8 bits, trois canaux, LZW, sans alpha et sans ICC 34675.
- MP3 vers WAV PCM 44,1 kHz, 16 bits, stéréo.
- Vidéo vers WAV avec extraction de la première piste audio.
- Conversion de plusieurs fichiers et téléchargement d’une archive ZIP avec rapport.

### Technique

- Version du renderer : `v2.1.0-shared-spectrum`.
- Registry de polices par utilisateur.
- Historique des conversions et fichiers de sortie séparés des MP4.
- Validation automatique des TIFF et WAV après conversion.

## 2.0.0 — 2 octobre 2026

### Produit

- Spectoom devient un studio interne de génération de vidéos musicales.
- Ajout des modules Nouvelle sortie et Spectrum YouTube.
- Suppression de toute logique Premium, paiement, quota commercial ou filigrane payant.
- La connexion sert à conserver les projets et les rendus.

### Interface

- Nouvelle charte claire inspirée d’une approche éditoriale noir/blanc avec accents pastel.
- Nouveau dashboard commun aux trois générateurs.
- Navigation latérale persistante.
- Éditeur guidé en six étapes avec aperçu central et audio en bas.
- Pages Mes projets, Bibliothèque, Rendus, Branding et Paramètres harmonisées.

### Entrées en playlist

- Conservation du moteur graphique fidèle aperçu/rendu.
- Conservation des six dispositions automatiques.
- Pictogrammes DSP noir/blanc et réglage Auto/Blanc/Noir.
- Lecture automatique de l’extrait lors du déplacement de la plage de 20 secondes.

### Nouvelle sortie

- Single, EP ou Album.
- Templates Portrait éditorial et Artwork central.
- Branding Virgin Music Afrique rouge, blanc ou noir.
- Extrait musical fixe de 20 secondes.
- Rendu MP4 1080 × 1350 de 20 secondes.

### Spectrum YouTube

- Rendu 1920 × 1080 sur toute la durée du morceau.
- Neuf styles de spectrum.
- Fond image ou vidéo.
- Palette à trois couleurs, sensibilité et typographie réglables.
- Aperçu Web Audio et rendu FFmpeg audio-réactif.
- Optimisation du pipeline : la scène statique est précomposée avant encodage.

### Technique

- Modèle de projet typé : `playlist_entry`, `new_release`, `youtube_spectrum`.
- Migration automatique des projets historiques.
- Dispatch de rendu par module avec API commune.
- Prévisualisations versionnées par manifeste.
- Contrôle automatique des MP4 avec FFprobe.
