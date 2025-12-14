[app]
title = SzamosSakk
package.name = szamossakk
package.domain = org.szamos

source.dir = .
source.include_exts = py

version = 0.2
requirements = python3,kivy

orientation = portrait
fullscreen = 0

# Ikon és splash (ha hozzáadod)
icon.filename = assets/icon.png
presplash.filename = assets/splash.png

android.api = 33
android.minapi = 21

[buildozer]
log_level = 2
warn_on_root = 1