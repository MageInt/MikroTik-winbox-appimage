# MikroTik WinBox — AppImage

Packaging du client [WinBox](https://mikrotik.com/software) de MikroTik en AppImage portable pour Linux x86_64.

## Contenu du dépôt

```
.
├── WinBox                  # Exécutable WinBox (ELF 64-bit)
├── AppRun                  # Point d'entrée de l'AppImage
├── WinBox.desktop          # Métadonnées de l'application
├── build-appimage.sh       # Script de build
└── assets/
    └── img/
        └── winbox.png      # Icône de l'application
```

## Prérequis

- OS Arch-based (CachyOS, Manjaro, EndeavourOS…)
- `patchelf` installé :
  ```bash
  sudo pacman -S patchelf
  ```
- `wget` et `ldd` (inclus par défaut sur Arch)
- Connexion internet (pour télécharger `appimagetool` et `linuxdeploy` au premier build)

## Build

```bash
git clone https://github.com/<your-username>/MikroTik-winbox-appimage
cd MikroTik-winbox-appimage
chmod +x build-appimage.sh
./build-appimage.sh
```

L'AppImage est générée à la racine du projet :

```
WinBox-x86_64.AppImage
```

## Utilisation

```bash
chmod +x WinBox-x86_64.AppImage
./WinBox-x86_64.AppImage
```

Ou double-cliquez dessus dans votre gestionnaire de fichiers (nécessite `libfuse2` ou le support FUSE de votre distro).

> **Note :** Les bibliothèques GPU (`libGL`, `libEGL`, `libvulkan`…) et la glibc ne sont **pas** bundlées — elles viennent de votre système hôte pour assurer la compatibilité avec vos pilotes graphiques.

## Dépendances runtime bundlées

Le script emballe automatiquement les bibliothèques Qt/X11 suivantes :

- `libxcb` et ses extensions (xcb-glx, xkb, randr, render…)
- `libxkbcommon`, `libX11`, `libfreetype`, `libfontconfig`
- `libdbus-1`, `libglib-2.0`, `libharfbuzz`
- Et toutes leurs dépendances transitives

## Licence

WinBox est un logiciel propriétaire de [MikroTik](https://mikrotik.com). Ce dépôt ne fournit que le packaging AppImage.
