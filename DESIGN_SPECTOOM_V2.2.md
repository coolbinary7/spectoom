# Spectoom 2.2 — notes de conception

## Formulaire de création

La modale générale utilise un état explicite :

- état initial sans sélection ;
- une seule carte active ;
- validation visuelle uniquement sur la carte active ;
- bouton principal indisponible tant que le choix est incomplet ;
- message sous le bouton indiquant l'éditeur qui sera ouvert.

Dans les onglets spécialisés, la modale devient contextuelle et n'affiche qu'un résumé du générateur choisi.

## Spectrum YouTube

Le logo est traité comme une option de branding et non comme un élément obligatoire. L'interface utilise un interrupteur clair :

- désactivé : aucun logo dans l'aperçu ni dans le MP4 ;
- activé : choix de variante ou import d'un logo personnel.

Le catalogue est limité à six styles pour réduire la charge cognitive et concentrer la qualité visuelle : Barres, Miroir, Fluide, Colline, LED et Particules.

Sur desktop large, l'éditeur conserve trois colonnes. Sur une largeur intermédiaire, le panneau de contrôle de droite passe sous la zone principale afin de préserver la taille du preview 16:9 et d'éviter le chevauchement des champs.

## Conversion

Le résultat suit une règle directe :

- 1 entrée → 1 sortie ;
- N entrées, avec N supérieur à 1 → 1 pack ZIP.

Le sélecteur de fichiers n'impose pas une liste fermée d'extensions audio. Le serveur inspecte d'abord le contenu, puis délègue le décodage à FFmpeg. L'interface affiche « Détection automatique » lorsqu'elle ne reconnaît pas l'extension avant l'envoi.
