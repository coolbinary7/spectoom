# Spectoom 2.2.2 Cloud

Version prête à être placée dans un dépôt GitHub privé et déployée comme service Docker avec stockage persistant.

## Fonctions conservées

- Entrées en playlist ;
- Nouvelles sorties ;
- Spectrum YouTube ;
- conversion image/audio/vidéo ;
- imports de polices ;
- comptes internes ;
- projets, rendus et historique persistants ;
- FFmpeg et FFprobe inclus dans l'image Docker.

## Démarrage local Docker

Copier `.env.example` vers `.env`, remplacer les identifiants, puis :

```bash
docker build -t spectoom .
docker run --rm --env-file .env -p 10000:10000 -v spectoom-data:/var/data spectoom
```

Ouvrir `http://127.0.0.1:10000`.

## Déploiement

Voir [`DEPLOIEMENT_GITHUB_RENDER.md`](DEPLOIEMENT_GITHUB_RENDER.md).
