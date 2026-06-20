# -*- coding: utf-8 -*-
"""
Suivi Hôtel des Ventes — interface native PyQt6 stylée WoW.
"""

import os
import sys
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QLineEdit, QFileDialog, QMessageBox, QStyleOption, QStyle,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen

import config
import tsm_parser as tsm
from item_names import ItemNames

try:
    import winsound
    HAS_SOUND = True
except Exception:
    HAS_SOUND = False


# ── Palette WoW ───────────────────────────────────────────────────────────────
OR     = "#ffd100"
OR_F   = "#b8932f"
BRONZE = "#6b5a2f"
FOND   = "#1a1410"
PANNEAU = "#221a12"
TEXTE  = "#f0e6d2"
DOUX   = "#c9b285"
RARE   = "#4a9eff"
VERT   = "#3fbf6f"
ORA    = "#e0a92f"
ROUGE  = "#e0533f"

QSS = f"""
QWidget {{
    background: {FOND};
    color: {TEXTE};
    font-family: 'Segoe UI', 'Trebuchet MS';
    font-size: 13px;
    border: none;
    outline: none;
}}
QMainWindow {{ background: {FOND}; }}
QDialog      {{ background: {FOND}; }}

QPushButton {{
    background: qlineargradient(y1:0,y2:1, stop:0 #2e2316, stop:1 #1c150b);
    color: {TEXTE};
    border: 1px solid {BRONZE};
    border-radius: 4px;
    padding: 5px 13px;
}}
QPushButton:hover   {{ border-color: {OR}; color: {OR}; }}
QPushButton:pressed {{ background: #1c150b; }}
QPushButton#principal {{
    background: qlineargradient(y1:0,y2:1, stop:0 #5a4420, stop:1 #2e2210);
    border-color: {OR}; color: {OR}; font-weight: bold;
}}

QComboBox {{
    background: qlineargradient(y1:0,y2:1, stop:0 #2e2316, stop:1 #1c150b);
    color: {TEXTE};
    border: 1px solid {BRONZE};
    border-radius: 4px;
    padding: 5px 8px;
    min-width: 140px;
}}
QComboBox:hover {{ border-color: {OR}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {PANNEAU};
    color: {TEXTE};
    border: 1px solid {BRONZE};
    selection-background-color: #3a2c1a;
    selection-color: {OR};
    outline: none;
}}

QCheckBox {{ color: {DOUX}; spacing: 6px; font-size: 12px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {BRONZE}; border-radius: 3px; background: #1c150b;
}}
QCheckBox::indicator:checked {{ background: {OR_F}; border-color: {OR}; }}

QTableWidget {{
    background: {FOND};
    alternate-background-color: #1f180f;
    color: {TEXTE};
    gridline-color: #2a2018;
    border: 1px solid {BRONZE};
    selection-background-color: rgba(255,209,0,25);
    selection-color: {TEXTE};
}}
QTableWidget::item {{ padding: 0px 10px; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{
    background: qlineargradient(y1:0,y2:1, stop:0 #3a2c1a, stop:1 #241a10);
    color: {OR};
    border: none;
    border-right: 1px solid {BRONZE};
    border-bottom: 2px solid {OR_F};
    padding: 6px 10px;
    font-size: 11px;
    font-weight: bold;
}}
QHeaderView::section:hover  {{ color: #fff; }}
QHeaderView::section:last   {{ border-right: none; }}

QScrollBar:vertical {{
    background: #140f08; width: 10px; border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {BRONZE}; border-radius: 5px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QLineEdit {{
    background: {PANNEAU};
    color: {TEXTE};
    border: 1px solid {BRONZE};
    border-radius: 4px;
    padding: 6px 9px;
}}
QLineEdit:focus {{ border-color: {OR_F}; }}
"""


# ── Threads ───────────────────────────────────────────────────────────────────

class NameLoader(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal()

    def __init__(self, names, items):
        super().__init__()
        self.names = names
        self.items = items

    def run(self):
        self.names.prefetch(self.items, progress=lambda i, t: self.progress.emit(i, t))
        self.finished.emit()


class UpdateChecker(QThread):
    update_found = pyqtSignal(str, str)

    def run(self):
        version, url = config.check_update()
        if version:
            self.update_found.emit(version, url)


class FileWatcher(QThread):
    changed = pyqtSignal()

    def __init__(self, path_getter, mtime_getter):
        super().__init__()
        self._path_getter = path_getter
        self._mtime_getter = mtime_getter
        self._running = True

    def run(self):
        while self._running:
            try:
                path = self._path_getter()
                if path and os.path.exists(path):
                    m = os.path.getmtime(path)
                    if m > self._mtime_getter() + 0.5:
                        self.changed.emit()
            except Exception:
                pass
            time.sleep(5)

    def stop(self):
        self._running = False


# ── Widgets ───────────────────────────────────────────────────────────────────

class WoWFrame(QFrame):
    """Cadre principal avec bordure dorée et coins ornementés."""

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

        pen = QPen(QColor(OR))
        pen.setWidth(2)
        p.setPen(pen)
        s = 16
        r = self.rect().adjusted(2, 2, -2, -2)
        for x1, y1, x2, y2, x3, y3 in [
            (r.left(),     r.top() + s, r.left(),  r.top(),    r.left() + s, r.top()),
            (r.right() - s, r.top(),    r.right(), r.top(),    r.right(),    r.top() + s),
            (r.left(),     r.bottom() - s, r.left(),  r.bottom(), r.left() + s,  r.bottom()),
            (r.right() - s, r.bottom(), r.right(), r.bottom(), r.right(),    r.bottom() - s),
        ]:
            p.drawLine(x1, y1, x2, y2)
            p.drawLine(x2, y2, x3, y3)
        p.end()


class StatCard(QFrame):
    def __init__(self, label):
        super().__init__()
        self.setFixedHeight(72)
        self.setMinimumWidth(160)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(y1:0,y2:1, stop:0 #2a2014, stop:1 #1a130a);
                border: 1px solid {BRONZE};
                border-radius: 6px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(2)

        lbl = QLabel(label.upper())
        lbl.setStyleSheet(f"color: {DOUX}; font-size: 10px; letter-spacing: 0.5px; background: transparent;")
        lay.addWidget(lbl)

        self.val = QLabel("—")
        self.val.setStyleSheet(f"color: {TEXTE}; font-size: 20px; font-weight: bold; background: transparent;")
        lay.addWidget(self.val)

    def set_value(self, text, gold=False):
        color = OR if gold else TEXTE
        self.val.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold; background: transparent;")
        self.val.setText(text)


class AlertBanner(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(y1:0,y2:1, stop:0 #1a3050, stop:1 #0e1d35);
                border: 1px solid {RARE};
                border-radius: 5px;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(10)

        bell = QLabel("🔔")
        bell.setStyleSheet("font-size: 16px; background: transparent;")
        lay.addWidget(bell)

        self.lbl = QLabel()
        self.lbl.setStyleSheet(f"color: #bcdcff; font-size: 13px; background: transparent;")
        lay.addWidget(self.lbl)
        lay.addStretch()
        self.hide()

    def show_alert(self, nouvelles):
        total = sum(nouvelles.values())
        detail = ", ".join(f"{v} sur {p}" for p, v in nouvelles.items())
        self.lbl.setText(f"{total} nouvelle(s) vente(s) depuis la dernière fois  ({detail})")
        self.show()

    def hide_alert(self):
        self.hide()


# ── Dialogue Réglages ─────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    saved = pyqtSignal(dict)

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.setWindowTitle("Réglages")
        self.setFixedSize(520, 370)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(8)

        lay.addWidget(self._lbl("Fichier TradeSkillMaster.lua"))
        row = QHBoxLayout()
        self.e_file = QLineEdit(cfg.get("tsm_file", ""))
        row.addWidget(self.e_file)
        btn = QPushButton("Parcourir…")
        btn.clicked.connect(self._browse)
        row.addWidget(btn)
        lay.addLayout(row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {BRONZE}; max-height: 1px;")
        lay.addSpacing(8)
        lay.addWidget(sep)
        lay.addSpacing(4)

        titre_api = QLabel("Clés API Blizzard (pour afficher les noms d'objets)")
        titre_api.setStyleSheet(f"color: {TEXTE}; font-weight: bold; background: transparent;")
        lay.addWidget(titre_api)

        note = QLabel("Gratuit sur develop.battle.net/access/clients")
        note.setStyleSheet(f"color: {DOUX}; font-size: 11px; background: transparent;")
        lay.addWidget(note)
        lay.addSpacing(4)

        lay.addWidget(self._lbl("Client ID"))
        self.e_cid = QLineEdit(cfg.get("blizzard_client_id", ""))
        lay.addWidget(self.e_cid)

        lay.addWidget(self._lbl("Client Secret"))
        self.e_cs = QLineEdit(cfg.get("blizzard_client_secret", ""))
        self.e_cs.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self.e_cs)

        lay.addWidget(self._lbl("Région"))
        self.c_region = QComboBox()
        self.c_region.addItems(["eu", "us", "kr", "tw"])
        self.c_region.setCurrentText(cfg.get("region", "eu"))
        lay.addWidget(self.c_region)

        lay.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Enregistrer")
        btn_ok.setObjectName("principal")
        btn_ok.clicked.connect(self._save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        lay.addLayout(btns)

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color: {DOUX}; font-size: 12px; background: transparent;")
        return l

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir TradeSkillMaster.lua", "",
            "Fichier TSM (TradeSkillMaster.lua);;Tous (*.*)")
        if path:
            self.e_file.setText(path)

    def _save(self):
        self.saved.emit({
            "tsm_file": self.e_file.text(),
            "blizzard_client_id": self.e_cid.text().strip(),
            "blizzard_client_secret": self.e_cs.text().strip(),
            "region": self.c_region.currentText(),
        })
        self.accept()


# ── Fenêtre principale ────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Suivi Hôtel des Ventes  v{config.VERSION}")
        self.setMinimumSize(860, 560)
        self.resize(980, 660)

        self.cfg   = config.load_config()
        self.state = config.load_state()
        self.names = self._make_names()
        self.data  = None
        self._watch_mtime = 0
        self._sort_col = 3
        self._sort_asc = False
        self._loader = None

        self._build_ui()
        self._post_init()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(0)

        cadre = WoWFrame()
        cadre.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(y1:0,y2:1, stop:0 #211a12, stop:1 #181208);
                border: 2px solid {OR_F};
            }}
        """)
        root.addWidget(cadre)
        cadre_lay = QVBoxLayout(cadre)
        cadre_lay.setContentsMargins(0, 0, 0, 0)
        cadre_lay.setSpacing(0)

        # En-tête
        entete = QFrame()
        entete.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(y1:0,y2:1, stop:0 #3a2c1a, stop:1 #241a10);
                border: none;
                border-bottom: 2px solid {OR_F};
            }}
        """)
        e_lay = QHBoxLayout(entete)
        e_lay.setContentsMargins(16, 10, 16, 10)
        e_lay.setSpacing(10)

        blason = QLabel("⚜")
        blason.setFixedSize(34, 34)
        blason.setAlignment(Qt.AlignmentFlag.AlignCenter)
        blason.setStyleSheet(f"""
            color: #3a2700; font-size: 18px;
            background: qradialgradient(cx:0.35,cy:0.3,radius:1,
                stop:0 #ffe680, stop:0.6 #b8932f, stop:1 #6b4a12);
            border: 2px solid #2a1f0c;
            border-radius: 17px;
        """)
        e_lay.addWidget(blason)

        titre = QLabel("Suivi Hôtel des Ventes")
        titre.setStyleSheet(f"color: {OR}; font-size: 17px; font-weight: bold; background: transparent;")
        e_lay.addWidget(titre)
        e_lay.addStretch()

        lbl_perso = QLabel("Personnage")
        lbl_perso.setStyleSheet(f"color: {DOUX}; font-size: 12px; background: transparent;")
        e_lay.addWidget(lbl_perso)

        self.combo_perso = QComboBox()
        self.combo_perso.currentTextChanged.connect(self._on_perso_changed)
        e_lay.addWidget(self.combo_perso)

        btn_refresh = QPushButton("⟳  Actualiser")
        btn_refresh.setObjectName("principal")
        btn_refresh.clicked.connect(self.reload_file)
        e_lay.addWidget(btn_refresh)

        self.chk_son = QCheckBox("Son")
        self.chk_son.setChecked(self.cfg.get("sound_enabled", True))
        self.chk_son.stateChanged.connect(self._toggle_sound)
        e_lay.addWidget(self.chk_son)

        btn_reglages = QPushButton("⚙  Réglages")
        btn_reglages.clicked.connect(self._open_settings)
        e_lay.addWidget(btn_reglages)

        cadre_lay.addWidget(entete)

        # Corps
        corps = QWidget()
        corps.setStyleSheet("QWidget { background: transparent; }")
        c_lay = QVBoxLayout(corps)
        c_lay.setContentsMargins(16, 12, 16, 0)
        c_lay.setSpacing(10)

        self.alerte = AlertBanner()
        c_lay.addWidget(self.alerte)

        stats_lay = QHBoxLayout()
        stats_lay.setSpacing(12)
        self.card_revenu = StatCard("Revenu total")
        self.card_ventes = StatCard("Ventes réalisées")
        self.card_objets = StatCard("Objets différents")
        stats_lay.addWidget(self.card_revenu)
        stats_lay.addWidget(self.card_ventes)
        stats_lay.addWidget(self.card_objets)
        stats_lay.addStretch()
        c_lay.addLayout(stats_lay)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Objet", "Vendus", "Expirés", "Revenu total", "Prix moyen", "Réussite"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(28)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col, w in [(1, 80), (2, 80), (3, 150), (4, 130), (5, 90)]:
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(col, w)
        hdr.sectionClicked.connect(self._on_header_clicked)

        c_lay.addWidget(self.table)
        cadre_lay.addWidget(corps)

        # Statut
        self.lbl_statut = QLabel("")
        self.lbl_statut.setStyleSheet(
            f"color: {DOUX}; font-size: 11px; padding: 4px 16px; "
            f"border-top: 1px solid #2a2018; background: transparent;")
        cadre_lay.addWidget(self.lbl_statut)

        pied = QLabel("Données issues de TradeSkillMaster · Hôtel des ventes uniquement")
        pied.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pied.setStyleSheet(
            f"color: {DOUX}; font-size: 10px; padding: 6px; "
            f"border-top: 1px solid #2a2018; background: transparent;")
        cadre_lay.addWidget(pied)

    # ── Logique ───────────────────────────────────────────────────────────────

    def _post_init(self):
        if not self.cfg.get("tsm_file") or not os.path.exists(self.cfg["tsm_file"]):
            QTimer.singleShot(300, self._prompt_file)
        else:
            self.reload_file()

        self._watcher = FileWatcher(
            lambda: self.cfg.get("tsm_file", ""),
            lambda: self._watch_mtime,
        )
        self._watcher.changed.connect(self.reload_file)
        self._watcher.start()

        checker = UpdateChecker(self)
        checker.update_found.connect(self._notify_update)
        checker.start()

    def _make_names(self):
        return ItemNames(
            config.cache_path(),
            client_id=self.cfg.get("blizzard_client_id", ""),
            client_secret=self.cfg.get("blizzard_client_secret", ""),
            region=self.cfg.get("region", "eu"),
            locale=self.cfg.get("locale", "fr_FR"),
        )

    def _prompt_file(self):
        QMessageBox.information(
            self, "Configuration",
            "Sélectionnez votre fichier TradeSkillMaster.lua.\n\n"
            "Il se trouve dans :\n"
            "World of Warcraft\\_retail_\\WTF\\Account\\"
            "VOTRE_COMPTE\\SavedVariables\\TradeSkillMaster.lua")
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir TradeSkillMaster.lua", "",
            "Fichier TSM (TradeSkillMaster.lua);;Tous (*.*)")
        if path:
            self.cfg["tsm_file"] = path
            config.save_config(self.cfg)
            self.reload_file()

    def reload_file(self):
        path = self.cfg.get("tsm_file", "")
        if not path or not os.path.exists(path):
            self._set_statut("Aucun fichier TSM sélectionné.")
            return
        try:
            self.data = tsm.load(path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de lire le fichier :\n{e}")
            return
        self._watch_mtime = os.path.getmtime(path)

        players = ["Tous"] + self.data["players"]
        prev = self.combo_perso.currentText()
        self.combo_perso.blockSignals(True)
        self.combo_perso.clear()
        self.combo_perso.addItems(players)
        last = self.cfg.get("last_player", "")
        if last in players:
            self.combo_perso.setCurrentText(last)
        elif prev in players:
            self.combo_perso.setCurrentText(prev)
        else:
            self.combo_perso.setCurrentText("Tous")
        self.combo_perso.blockSignals(False)

        prev_count = self.state.get("sales_count_by_player", {})
        nouvelles, current = tsm.detect_new_sales(self.data, prev_count)
        self.state["sales_count_by_player"] = current
        config.save_state(self.state)
        if nouvelles:
            self.alerte.show_alert(nouvelles)
            self._play_sound()
        else:
            self.alerte.hide_alert()

        self._refresh_table()
        self._set_statut("Récupération des noms d'objets…")
        items = [r["itemString"] for r in self.data["sales"]]
        self._loader = NameLoader(self.names, items)
        self._loader.progress.connect(lambda i, t: self._set_statut(f"Noms d'objets : {i}/{t}"))
        self._loader.finished.connect(self._on_names_loaded)
        self._loader.start()

    def _on_names_loaded(self):
        self._refresh_table()
        self._set_statut("Prêt.")

    def _refresh_table(self):
        if not self.data:
            return
        player = self.combo_perso.currentText()
        sel = None if player in ("", "Tous") else player
        rows = tsm.compute_profitability(self.data, player=sel, source="Auction")

        total = sum(r["revenu_total"] for r in rows)
        nb    = sum(r["nb_transactions"] for r in rows)
        self.card_revenu.set_value(tsm.copper_to_gold_str(total), gold=True)
        self.card_ventes.set_value(str(nb))
        self.card_objets.set_value(str(len(rows)))

        rows = self._sort_rows(rows)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            name = self.names.get(r["itemString"])
            taux = r["taux_reussite"]
            c_taux = VERT if taux >= 75 else (ORA if taux >= 50 else ROUGE)
            cells = [
                (name,                                   RARE,  Qt.AlignmentFlag.AlignLeft),
                (str(r["qte_vendue"]),                   TEXTE, Qt.AlignmentFlag.AlignRight),
                (str(r["qte_expiree"]),                  TEXTE, Qt.AlignmentFlag.AlignRight),
                (tsm.copper_to_gold_str(r["revenu_total"]), OR, Qt.AlignmentFlag.AlignRight),
                (tsm.copper_to_gold_str(r["prix_moyen"]),  DOUX, Qt.AlignmentFlag.AlignRight),
                (f"{taux}%",                             c_taux, Qt.AlignmentFlag.AlignRight),
            ]
            for j, (text, color, align) in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(i, j, item)

    def _on_header_clicked(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = (col == 0)
        self._refresh_table()

    def _sort_rows(self, rows):
        keymap = {
            0: lambda r: self.names.get(r["itemString"]).lower(),
            1: lambda r: r["qte_vendue"],
            2: lambda r: r["qte_expiree"],
            3: lambda r: r["revenu_total"],
            4: lambda r: r["prix_moyen"],
            5: lambda r: r["taux_reussite"],
        }
        return sorted(rows, key=keymap.get(self._sort_col, keymap[3]),
                      reverse=not self._sort_asc)

    def _on_perso_changed(self, text):
        if text:
            self.cfg["last_player"] = text
            config.save_config(self.cfg)
            self._refresh_table()

    def _toggle_sound(self):
        self.cfg["sound_enabled"] = self.chk_son.isChecked()
        config.save_config(self.cfg)

    def _play_sound(self):
        if self.chk_son.isChecked() and HAS_SOUND:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    def _open_settings(self):
        dlg = SettingsDialog(self, self.cfg)
        dlg.setStyleSheet(QSS)
        dlg.saved.connect(self._on_settings_saved)
        dlg.exec()

    def _on_settings_saved(self, new_cfg):
        self.cfg.update(new_cfg)
        config.save_config(self.cfg)
        self.names = self._make_names()
        self.reload_file()

    def _notify_update(self, version, url):
        if QMessageBox.question(
            self, "Mise à jour disponible",
            f"Une nouvelle version ({version}) est disponible.\n"
            f"Vous utilisez la version {config.VERSION}.\n\n"
            "Ouvrir la page de téléchargement ?",
        ) == QMessageBox.StandardButton.Yes:
            import webbrowser
            webbrowser.open(url)

    def _set_statut(self, text):
        self.lbl_statut.setText(text)

    def closeEvent(self, event):
        if hasattr(self, "_watcher"):
            self._watcher.stop()
        super().closeEvent(event)


# ── Point d'entrée ────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)

    if os.name == "nt":
        try:
            from ctypes import windll
            windll.shell32.SetCurrentProcessExplicitAppUserModelID("SuiviHDV.1.0")
        except Exception:
            pass

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
