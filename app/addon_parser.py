# -*- coding: utf-8 -*-
"""
Lecture du fichier SuiviHDV.lua (SavedVariables de notre addon).
Format : tables Lua simples, parsées par regex sans dépendance externe.
"""

import re


def _extract_block(text, key):
    """Retourne le contenu de ["key"] = { ... } par comptage de niveaux de braces."""
    m = re.search(r'\["' + re.escape(key) + r'"\]\s*=\s*\{', text)
    if not m:
        return None
    start = m.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    return text[start:i - 1]


def load(path):
    """
    Lit SuiviHDV.lua et retourne un dict structuré :
    {
      "joueur": str,
      "realm": str,
      "derniere_maj": int,
      "scan_complet": bool,
      "items": { item_id(int): {"qte": int, "prix_min": int} },
      "mes_annonces": [ {"item": int, "qte": int, "prix": int} ],
      "mes_ventes":   [ {"sujet": str, "total": int, "t": int} ],
    }
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    def _str(key):
        m = re.search(r'\["' + key + r'"\]\s*=\s*"([^"]*)"', text)
        return m.group(1) if m else ""

    def _int(key):
        m = re.search(r'\["' + key + r'"\]\s*=\s*(\d+)', text)
        return int(m.group(1)) if m else 0

    def _bool(key):
        m = re.search(r'\["' + key + r'"\]\s*=\s*(true|false)', text)
        return m and m.group(1) == "true"

    joueur       = _str("joueur")
    realm        = _str("realm")
    derniere_maj = _int("derniere_maj")
    scan_complet = _bool("scan_complet")

    # -- items : [12345] = { ["p"] = X, ["q"] = Y, ["t"] = Z } (ordre quelconque)
    items = {}
    items_block = _extract_block(text, "items")
    if items_block:
        for entry_m in re.finditer(r'\[(\d+)\]\s*=\s*\{([^{}]*)\}', items_block):
            item_id = int(entry_m.group(1))
            entry   = entry_m.group(2)
            q_m = re.search(r'\["q"\]\s*=\s*(\d+)', entry)
            p_m = re.search(r'\["p"\]\s*=\s*(\d+)', entry)
            if q_m and p_m:
                items[item_id] = {
                    "qte":      int(q_m.group(1)),
                    "prix_min": int(p_m.group(1)),
                }

    # -- mes_annonces : { ["q"] = X, ["p"] = Y, ["item"] = Z } (ordre quelconque)
    mes_annonces = []
    ann_block = _extract_block(text, "mes_annonces")
    if ann_block:
        for entry_m in re.finditer(r'\{([^{}]*)\}', ann_block):
            entry  = entry_m.group(1)
            item_m = re.search(r'\["item"\]\s*=\s*(\d+)', entry)
            q_m    = re.search(r'\["q"\]\s*=\s*(\d+)', entry)
            p_m    = re.search(r'\["p"\]\s*=\s*(\d+)', entry)
            tls_m  = re.search(r'\["tls"\]\s*=\s*(\d+)', entry)
            t_m    = re.search(r'\["t"\]\s*=\s*(\d+)', entry)
            if item_m and q_m and p_m:
                mes_annonces.append({
                    "item": int(item_m.group(1)),
                    "qte":  int(q_m.group(1)),
                    "prix": int(p_m.group(1)),
                    "tls":  int(tls_m.group(1)) if tls_m else 0,
                    "t":    int(t_m.group(1))   if t_m   else 0,
                })

    # -- mes_ventes : { ["sujet"] = "...", ["total"] = X, ["t"] = Y } (ordre quelconque)
    mes_ventes = []
    ven_block = _extract_block(text, "mes_ventes")
    if ven_block:
        for entry_m in re.finditer(r'\{([^{}]*)\}', ven_block):
            entry  = entry_m.group(1)
            suj_m  = re.search(r'\["sujet"\]\s*=\s*"([^"]*)"', entry)
            tot_m  = re.search(r'\["total"\]\s*=\s*(\d+)', entry)
            t_m    = re.search(r'\["t"\]\s*=\s*(\d+)', entry)
            if suj_m and tot_m and t_m:
                mes_ventes.append({
                    "sujet": suj_m.group(1),
                    "total": int(tot_m.group(1)),
                    "t":     int(t_m.group(1)),
                })

    # -- or_par_joueur : { ["Goldloum"] = 123456 }
    or_par_joueur = {}
    or_block = _extract_block(text, "or_par_joueur")
    if or_block:
        for m in re.finditer(r'\["([^"]+)"\]\s*=\s*(\d+)', or_block):
            or_par_joueur[m.group(1)] = int(m.group(2))

    return {
        "joueur":        joueur,
        "realm":         realm,
        "derniere_maj":  derniere_maj,
        "scan_complet":  scan_complet,
        "items":         items,
        "mes_annonces":  mes_annonces,
        "mes_ventes":    mes_ventes,
        "or_par_joueur": or_par_joueur,
    }
