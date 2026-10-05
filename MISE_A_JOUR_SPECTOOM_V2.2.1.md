# Mise à jour Spectoom 2.2.1

## Objet du correctif

Spectoom 2.2.0 pouvait convertir correctement un média puis échouer au moment du téléchargement lorsque le nom du résultat contenait des espaces, des accents ou d’autres caractères encodés dans l’URL.

Le navigateur recevait alors une réponse d’erreur JSON au lieu du fichier `.tiff`, `.wav` ou `.zip`. Chrome pouvait afficher le nom du téléchargement avec l’extension `.json` et le message « Fichier non disponible sur le site ».

Spectoom 2.2.1 corrige le circuit de téléchargement :

- décodage correct des noms de fichiers dans `/media/conversions/` ;
- URL encodée de façon sûre pour les nouveaux résultats ;
- nom de téléchargement UTF-8 compatible avec un nom ASCII de secours ;
- récupération possible des conversions déjà terminées en V2.2.0 ;
- aucun changement du format des projets ni des médias existants.

## Installation du correctif sous Windows

1. Fermer Spectoom et toutes les fenêtres noires qui exécutent `server.py`.
2. Décompresser entièrement `spectoom-v2.2.1-correctif-conversion.zip`.
3. Ouvrir le dossier `spectoom-update-2.2.1`.
4. Double-cliquer sur `UPDATE_SPECTOOM_V2.2.1.bat`.
5. Si le dossier n’est pas détecté automatiquement, sélectionner celui qui contient directement :

```text
server.py
static
data
run.bat
```

L’installateur sauvegarde `data/store.json` dans `data/backups`, remplace les fichiers applicatifs et conserve :

- les comptes ;
- les projets ;
- les uploads ;
- les polices ;
- les MP4 ;
- les TIFF, WAV et ZIP déjà générés ;
- l’historique des conversions.

## Vérification

Après le redémarrage, ouvrir :

```text
http://127.0.0.1:8080/api/health
```

Le résultat doit contenir :

```json
{
  "ok": true,
  "service": "Spectoom",
  "version": "2.2.1"
}
```

Dans l’onglet Conversion :

1. envoyer une image ou un fichier audio dont le nom contient des espaces ;
2. attendre l’état `Terminé` ;
3. cliquer sur `Fichier` ;
4. vérifier que le navigateur télécharge directement un `.tiff` ou un `.wav`, et non un `.json`.

Un lot de plusieurs fichiers continue de produire un ZIP.

## Installation complète

Pour une installation propre, décompresser `spectoom-v2.2.1-complet.zip`, ouvrir le dossier `spectoom`, puis lancer `run.bat`.
