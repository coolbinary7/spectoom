# Déployer Spectoom avec GitHub + Render

## Architecture retenue

- **GitHub privé** : code source, historique, revue et tests CI.
- **Render Web Service Docker** : exécution du serveur Python et de FFmpeg.
- **Disque persistant Render** : comptes, projets, médias, polices, rendus et conversions.
- **HTTPS Render** : certificat automatique et cookie de session sécurisé.

GitHub Pages n'est pas utilisé : Spectoom a besoin d'un serveur Python, de FFmpeg et d'un stockage persistant.

## 1. Créer le dépôt GitHub

Créer un dépôt privé nommé `spectoom`, puis envoyer tous les fichiers de ce dossier sur la branche `main`.

Ne jamais ajouter le contenu du dossier `data` au dépôt. Le fichier `.gitignore` le bloque volontairement.

## 2. Vérifier GitHub Actions

Après le premier push, ouvrir l'onglet **Actions** du dépôt. Le workflow `Spectoom CI` vérifie :

- la syntaxe Python et JavaScript ;
- le démarrage du serveur ;
- l'endpoint `/api/health` ;
- la connexion d'un compte interne ;
- la construction de l'image Docker.

## 3. Créer le service Render

1. Ouvrir Render et connecter le compte GitHub.
2. Choisir **New Blueprint Instance**.
3. Sélectionner le dépôt privé `spectoom`.
4. Render détecte automatiquement `render.yaml`.
5. Renseigner les six secrets demandés :
   - `SPECTOOM_USER_NAME`
   - `SPECTOOM_USER_EMAIL`
   - `SPECTOOM_USER_PASSWORD`
   - `SPECTOOM_ADMIN_NAME`
   - `SPECTOOM_ADMIN_EMAIL`
   - `SPECTOOM_ADMIN_PASSWORD`
6. Valider le déploiement.

Le Blueprint crée un service Docker sur un plan 2 CPU / 4 Go de RAM et un disque persistant de 20 Go. Ces valeurs peuvent être ajustées dans `render.yaml` avant le premier déploiement.

## 4. Contrôler le déploiement

Ouvrir :

```text
https://VOTRE-SERVICE.onrender.com/api/health
```

Le JSON doit notamment contenir :

```json
{
  "ok": true,
  "service": "Spectoom",
  "version": "2.2.2-cloud",
  "environment": "production",
  "storageWritable": true
}
```

Puis ouvrir la racine du site et se connecter avec le compte interne configuré dans Render.

## 5. Domaine personnalisé

Dans Render : **Settings > Custom Domains**. Ajouter le sous-domaine souhaité, par exemple `app.spectoom.com`, puis appliquer les enregistrements DNS indiqués par Render.

## 6. Mises à jour

Chaque push sur `main` :

1. déclenche les tests GitHub Actions ;
2. déclenche automatiquement un nouveau déploiement Render si l'auto-deploy est activé ;
3. remplace le code de l'application ;
4. conserve le disque `/var/data`, donc les projets et rendus.

Éviter de déployer pendant un rendu en cours : le service est mono-instance à cause du disque persistant et un redémarrage interrompt les tâches actives.

## 7. Sauvegardes

Render réalise des snapshots du disque, mais une sauvegarde applicative régulière reste recommandée. Les données importantes sont sous :

```text
/var/data/spectoom
```

Elles comprennent `store.json`, `uploads`, `renders`, `conversions`, `fonts` et `backups`.

## 8. Limites connues de cette première version cloud

- Une seule instance du service est utilisée.
- Les sessions sont en mémoire : un redéploiement demande une nouvelle connexion.
- Les rendus en cours sont interrompus par un redéploiement.
- `store.json` convient à un petit outil interne ; une montée en charge nécessitera PostgreSQL et un stockage objet.
