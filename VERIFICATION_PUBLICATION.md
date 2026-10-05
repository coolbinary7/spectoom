# Préparation de la publication

Contrôles effectués le 5 octobre 2026 sur l’archive fournie.

- Inventaire complet : code Python/JavaScript, styles, HTML, documentation, scripts, configuration et médias statiques. Les médias sous static/demo sont les ressources de démonstration livrées avec le produit ; aucun stockage utilisateur n’est présent dans l’archive.
- Recherche de secrets dans les fichiers texte : aucun secret réel identifié. Suppression des mots de passe de démonstration du code, du README et de la CI. Le modèle .env.example contient des champs de comptes vides.
- .gitignore et .dockerignore renforcés : environnement, données, uploads, rendus, conversions, sauvegardes, clés, bases locales, caches et archives. Exclusions Git contrôlées.
- Serveur : écoute par défaut sur 0.0.0.0, port fourni par PORT. HOST reste configurable.
- Stockage applicatif sous SPECTOOM_DATA_DIR. Correction de la résolution des médias sur un disque externe avec contrôle des chemins et des liens symboliques.
- Dockerfile inspecté : Python 3.12, dépendances, FFmpeg, polices, healthcheck utilisant PORT. Construction non exécutée : Docker absent.
- render.yaml inspecté : disque /var/data, données /var/data/spectoom, secrets via sync:false, une instance. Plan 2c-4g confirmé dans la documentation officielle https://render.com/docs/blueprint-spec ; aucun service Render créé.
- requirements.txt inspecté : Pillow, imageio-ffmpeg, mutagen avec bornes de versions. Environnement isolé installé : Pillow 12.3.0, imageio-ffmpeg 0.6.0, mutagen 1.48.1. pip check valide les dépendances.
- Syntaxe Python et JavaScript : valide.
- Tests JavaScript : 5 réussis.
- Tests Python : 4 réussis, dont démarrage HTTP réel, écoute sur 0.0.0.0 et PORT dynamique, connexion avec mot de passe aléatoire, stockage externe, protection des chemins et hachage des mots de passe. Les données de test sont temporaires et hors du dépôt.
- La CI exécute les tests Python et JavaScript ainsi que docker build.

Git initialisé sur main. Publication GitHub autorisée par l’utilisateur. Dépôt privé créé : https://github.com/coolbinary7/spectoom. Ce rapport consigne les contrôles précédant le commit initial ; le résultat de la CI distante est disponible dans l’onglet Actions. Aucun secret, fichier .env réel ou stockage utilisateur ne figure dans les fichiers préparés pour le commit.

Les rapports QA historiques de l’archive décrivent des vérifications antérieures ; ils ne constituent pas les résultats de cette session. Aucun rendu vidéo complet ni conversion audio n’a été exécuté durant cette préparation.
