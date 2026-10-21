# Mediatel (RANDROID) — application macOS native

GUI SwiftUI du gestionnaire mobile RANDROID. Construite **sans Xcode**
(Command Line Tools seuls). Pilote `adb`, `heimdall`, `odin4`.

## Fonctions (v1)
- Liste des appareils Android (adb), avec état (device / unauthorized / offline).
- Explorateur de fichiers : navigation, double-clic pour ouvrir un dossier, parent.
- Envoyer (push) un fichier local vers le dossier courant.
- Récupérer (pull) un élément sélectionné vers un dossier Mac.
- Flash firmware **légitime** : Heimdall (images de partition) et Odin4 (.tar.md5
  BL/AP/CP/CSC). Passage en mode Download, détection. Aucun contournement FRP/verrou.

## Construire
    ./scripts/build-app.sh
Produit `build/Mediatel.app` (icône .icns générée, signature ad-hoc).

## Premier lancement
Sans compte Apple Developer, pas de notarisation : au premier lancement, macOS
affiche « éditeur non identifié ». Comportement normal du système.
→ clic droit sur l'app → **Ouvrir** → **Ouvrir**. Ensuite double-clic suffit.

Pour l'installer : glisser `build/Mediatel.app` dans `/Applications`.

## Prérequis runtime
- `adb`            : brew install android-platform-tools
- `heimdall`       : brew install heimdall        (flash open source)
- `odin4`          : binaire à placer dans le PATH (protocole Samsung)

Note : lancée depuis le Finder, l'app hérite d'un PATH minimal ; le wrapper
`Shell` réinjecte /opt/homebrew/bin et les platform-tools Android.
