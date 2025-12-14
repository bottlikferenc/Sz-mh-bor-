[app]
# ===============================
# Alkalmazás alapadatok
# ===============================
title = SzamosSakk
package.name = szamossakk
package.domain = org.szamos

# ===============================
# Forráskód
# ===============================
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,wav,mp3

# ===============================
# Verzió
# ===============================
version = 0.2

# ===============================
# Követelmények
# FONTOS: python3-at NEM kell ide írni
# ===============================
requirements = kivy

# ===============================
# Képernyő
# ===============================
orientation = portrait
fullscreen = 0

# ===============================
# Android beállítások (STABIL)
# ===============================
android.api = 34
android.minapi = 21
android.build_tools = 34.0.0
android.accept_sdk_license = True

# ===============================
# Ikon / Splash (csak ha léteznek!)
# Ha nincs ilyen fájl, maradjon kikommentelve
# ===============================
# icon.filename = assets/icon.png
# presplash.filename = assets/splash.png

# ===============================
# Architektúrák
# ===============================
android.archs = arm64-v8a,armeabi-v7a

# ===============================
# Logolás
# ===============================
log_level = 2

# ===============================
# Buildozer beállítások
# ===============================
[buildozer]
warn_on_root = 1
