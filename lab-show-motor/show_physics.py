# -*- coding: utf-8 -*-
"""Física Live Jokers Show — 54 casillas."""
from __future__ import annotations

# Plato global
N_SLOTS = 54
N_R = 45
N_G = 9
P_G = N_G / N_SLOTS

# Urna R (freq empírica → 45)
URNA_R = {"R1": 21, "R2": 13, "R3": 7, "R4": 4}

# Menú G en plato (imagen humana; empírico G1↔G2)
MENU_G_HUMAN = {"G4": 1, "G3": 3, "G2": 2, "G1": 3}
MENU_G_EMP = {"G4": 1, "G3": 3, "G2": 3, "G1": 2}

# Menú L → tinta G (bitácora / E01)
MENU_L_BANDS = [
    (70, 99, "G3"),
    (100, 149, "G1G2"),  # moneda ~50/50
    (150, 9999, "G4"),
]

CORTE_LARGO_S = 70
