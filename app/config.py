# -*- coding: utf-8 -*-
"""
Configuration de l'appli (stockée dans %APPDATA%\\SuiviHDV) et
vérification des mises à jour via GitHub Releases.
"""

import json
import os
import urllib.request


APP_NAME = "SuiviHDV"
VERSION = "1.1.4"   # <-- numéro de version de CETTE build. À incrémenter à chaque release.

# Dépôt GitHub où sont publiées les releases.
GITHUB_OWNER = "maquairealexandre-ia"
GITHUB_REPO  = "SuiviHDV"


def config_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def config_path():
    return os.path.join(config_dir(), "config.json")


def cache_path():
    return os.path.join(config_dir(), "item_cache.json")


def icons_dir():
    d = os.path.join(config_dir(), "icons")
    os.makedirs(d, exist_ok=True)
    return d


def state_path():
    return os.path.join(config_dir(), "state.json")


DEFAULT_CONFIG = {
    "tsm_file": "",          # chemin vers TradeSkillMaster.lua (source legacy)
    "addon_file": "",        # chemin vers SuiviHDV.lua (notre addon)
    "realm_slug": "",        # slug du royaume pour l'API Blizzard (ex: "chogall")
    "connected_realm_id": 0, # résolu automatiquement depuis realm_slug
    "nas_url": "",           # ex: http://192.168.1.10:8765
    "nas_api_key": "",       # même valeur que API_KEY dans docker-compose.yml
    "blizzard_client_id": "",
    "blizzard_client_secret": "",
    "region": "eu",
    "locale": "fr_FR",
    "sound_enabled": True,
    "last_player": "",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    p = config_path()
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_state():
    p = state_path()
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state):
    try:
        with open(state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception:
        pass


def _version_tuple(v):
    return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())


def check_update():
    """
    Interroge GitHub pour la dernière release.
    Renvoie (nouvelle_version, url_telechargement, notes) ou (None, None, None).
    """
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        latest = data.get("tag_name", "")
        if not latest:
            return None, None, None
        if _version_tuple(latest) > _version_tuple(VERSION):
            dl = None
            # Priorité : installeur Inno Setup
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if "installeur" in name and name.endswith(".exe"):
                    dl = asset.get("browser_download_url")
                    break
            # Fallback : n'importe quel exe
            if dl is None:
                for asset in data.get("assets", []):
                    if asset.get("name", "").lower().endswith(".exe"):
                        dl = asset.get("browser_download_url")
                        break
            if dl is None:
                dl = data.get("html_url")
            notes = data.get("body", "").strip() or "Aucune note de version."
            return latest, dl, notes
    except Exception:
        return None, None, None
    return None, None, None
