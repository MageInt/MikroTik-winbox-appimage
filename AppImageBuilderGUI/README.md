# AppImage Builder GUI

Outil graphique universel pour créer des AppImages à partir de n'importe quel binaire Linux.

## Fonctionnalités

- **Sélection de binaire** avec auto-détection de la version et de l'architecture
- **Configuration complète** : nom, version, description, icône, catégories FreeDesktop
- **Gestion des bibliothèques** : bundling automatique via `linuxdeploy` avec liste d'exclusions configurable
- **Fichiers supplémentaires** : possibilité d'ajouter des fichiers/dossiers dans l'AppImage
- **Génération automatique** de `.desktop`, `AppRun`, et `appdata.xml`
- **Téléchargement automatique** de `appimagetool` et `linuxdeploy`
- **Interface sombre** moderne avec barre de progression et log en temps réel

## Prérequis

- Python 3.8+
- `tkinter` (inclus avec la plupart des distributions Python)
- `ldd` (inclus dans glibc)
- `patchelf` (`sudo pacman -S patchelf` / `sudo apt install patchelf`)
- `strings` (inclus dans binutils)
- `file` (inclus dans la plupart des distributions)

## Lancement

```bash
cd AppImageBuilderGUI
python3 main.py
```

## Utilisation

1. **Sélectionner le binaire** Linux source
2. Cliquer sur **Auto-detect** pour remplir automatiquement le nom, la version et l'architecture
3. Remplir les champs manquants (version si non détectée, description, etc.)
4. Sélectionner une **icône** (PNG ou SVG recommandé)
5. Choisir les **catégories** FreeDesktop
6. Ajuster la liste des **bibliothèques exclues** si nécessaire
7. Choisir le **dossier de sortie**
8. Cliquer sur **Construire l'AppImage**

L'outil va :
- Télécharger `appimagetool` et `linuxdeploy` (si pas déjà présents)
- Créer la structure `AppDir`
- Copier le binaire, l'icône et les fichiers supplémentaires
- Générer les fichiers `.desktop`, `AppRun` et `appdata.xml`
- Bundler les bibliothèques partagées
- Patcher le RPATH
- Empaqueter le tout en `.AppImage`

## Structure du projet

```
AppImageBuilderGUI/
├── main.py        # Point d'entrée
├── builder.py     # Logique de construction (AppImageConfig, AppImageBuilder)
├── gui.py         # Interface tkinter
└── README.md
```
