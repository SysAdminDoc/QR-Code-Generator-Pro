#!/usr/bin/env python3
"""
QR Code Generator Pro
A professional QR code maker with visual style gallery, multiple presets, and extensive customization.

Version: 7.0.0
Author: QR Code Generator Pro Team
Website: https://github.com/qrcodegenpro
License: MIT
"""

import sys
import os
import platform
import ctypes
import logging
from pathlib import Path
from datetime import datetime
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

# =============================================================================
# HIGH DPI AWARENESS (Windows)
# =============================================================================
if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# =============================================================================
# APPLICATION METADATA
# =============================================================================
APP_NAME = "QR Code Generator Pro"
APP_VERSION = "7.0.0"
APP_AUTHOR = "QR Code Generator Pro Team"
APP_WEBSITE = "https://github.com/qrcodegenpro"
APP_COPYRIGHT = f"© {datetime.now().year} {APP_AUTHOR}"
BUILD_DATE = datetime.now().strftime("%B %d, %Y")

# =============================================================================
# LOGGING SETUP
# =============================================================================
def get_app_data_dir():
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return Path(base) / "QRCodeGeneratorPro"
    elif platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "QRCodeGeneratorPro"
    else:
        return Path.home() / ".config" / "qrcodegeneratorpro"

APP_DATA_DIR = get_app_data_dir()
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = APP_DATA_DIR / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Starting {APP_NAME} v{APP_VERSION}")

# =============================================================================
# DEPENDENCY MANAGEMENT
# =============================================================================
REQUIRED_PACKAGES = {'qrcode': 'qrcode[pil]', 'PIL': 'Pillow'}

def check_dependencies():
    missing = []
    for module, package in REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append((module, package))
    return missing

def prompt_install_dependencies(missing_packages):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    packages_list = "\n".join([f"  • {pkg}" for _, pkg in missing_packages])
    result = messagebox.askyesno("First-Time Setup",
        f"{APP_NAME} requires:\n\n{packages_list}\n\nInstall now?", icon="question")
    root.destroy()
    return result

def install_dependencies(missing_packages):
    import subprocess
    import tkinter as tk
    from tkinter import ttk
    
    root = tk.Tk()
    root.title("Installing...")
    root.geometry("350x100")
    root.resizable(False, False)
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - 175
    y = (root.winfo_screenheight() // 2) - 50
    root.geometry(f"+{x}+{y}")
    
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    status_var = tk.StringVar(value="Installing...")
    ttk.Label(frame, textvariable=status_var).pack()
    progress = ttk.Progressbar(frame, mode='determinate', length=300)
    progress.pack(pady=10)
    
    success = True
    def run():
        nonlocal success
        for i, (_, pkg) in enumerate(missing_packages):
            status_var.set(f"Installing {pkg}...")
            progress['value'] = (i / len(missing_packages)) * 100
            root.update()
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                success = False
        progress['value'] = 100
        root.after(800, root.destroy)
    
    root.after(100, run)
    root.mainloop()
    return success

def ensure_dependencies():
    missing = check_dependencies()
    if not missing:
        return True
    if prompt_install_dependencies(missing):
        if install_dependencies(missing):
            return True
    return False

if not ensure_dependencies():
    sys.exit(1)

# =============================================================================
# IMPORTS
# =============================================================================
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    SquareModuleDrawer, GappedSquareModuleDrawer, CircleModuleDrawer,
    RoundedModuleDrawer, VerticalBarsDrawer, HorizontalBarsDrawer
)
from qrcode.image.styles.colormasks import (
    SolidFillColorMask, RadialGradiantColorMask, SquareGradiantColorMask,
    HorizontalGradiantColorMask, VerticalGradiantColorMask
)
from PIL import Image, ImageTk, ImageDraw


# =============================================================================
# MODULE DRAWERS
# =============================================================================
MODULE_DRAWER_CLASSES = {
    "square": SquareModuleDrawer,
    "rounded": RoundedModuleDrawer,
    "circle": CircleModuleDrawer,
    "gapped": GappedSquareModuleDrawer,
    "vertical_bars": VerticalBarsDrawer,
    "horizontal_bars": HorizontalBarsDrawer,
}

MODULE_DRAWER_NAMES = {
    "square": "Square",
    "rounded": "Rounded",
    "circle": "Circle",
    "gapped": "Gapped",
    "vertical_bars": "V-Bars",
    "horizontal_bars": "H-Bars",
}

# =============================================================================
# PRESET LIBRARY - 98 Families
# =============================================================================
PRESET_FAMILIES = {
    # TRANSPARENT SERIES
    "Transparent Black": {
        "fg_color": "#000000", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped", "vertical_bars"]
    },
    "Transparent White": {
        "fg_color": "#FFFFFF", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped", "vertical_bars"]
    },
    "Transparent Gray": {
        "fg_color": "#6B7280", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Transparent Navy": {
        "fg_color": "#1e3a5f", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Transparent Red": {
        "fg_color": "#DC2626", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Transparent Blue": {
        "fg_color": "#2563EB", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Transparent Green": {
        "fg_color": "#16A34A", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Transparent Purple": {
        "fg_color": "#7C3AED", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Transparent Orange": {
        "fg_color": "#EA580C", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Transparent Teal": {
        "fg_color": "#0D9488", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Transparent Pink": {
        "fg_color": "#EC4899", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Transparent Gold": {
        "fg_color": "#D4AF37", "bg_color": None, "transparent": True,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    
    # CLASSIC
    "Classic Black": {
        "fg_color": "#000000", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped", "vertical_bars", "horizontal_bars"]
    },
    "Inverted Classic": {
        "fg_color": "#FFFFFF", "bg_color": "#000000", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    
    # CORPORATE
    "Corporate Navy": {
        "fg_color": "#1e3a5f", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Corporate Blue": {
        "fg_color": "#1E40AF", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Corporate Gray": {
        "fg_color": "#374151", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Corporate Charcoal": {
        "fg_color": "#1F2937", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Corporate Teal": {
        "fg_color": "#0F766E", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Corporate Slate": {
        "fg_color": "#475569", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Corporate Indigo": {
        "fg_color": "#4338CA", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Corporate Forest": {
        "fg_color": "#166534", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    
    # HORIZONTAL GRADIENTS
    "Gradient Blue Purple": {
        "fg_color": "#667eea", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#667eea", "#764ba2"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Pink Orange": {
        "fg_color": "#f093fb", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#f093fb", "#f5576c"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Teal Green": {
        "fg_color": "#11998e", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#11998e", "#38ef7d"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Ocean": {
        "fg_color": "#2193b0", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#2193b0", "#6dd5ed"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Sunset": {
        "fg_color": "#f12711", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#f12711", "#f5af19"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Forest": {
        "fg_color": "#134e5e", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#134e5e", "#71b280"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Candy": {
        "fg_color": "#fc466b", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#fc466b", "#3f5efb"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Mint": {
        "fg_color": "#0cebeb", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#0cebeb", "#20e3b2"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Peach": {
        "fg_color": "#ed6ea0", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#ed6ea0", "#ec8c69"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Aurora": {
        "fg_color": "#7f7fd5", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#7f7fd5", "#91eae4"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Royal": {
        "fg_color": "#141e30", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#141e30", "#243b55"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Cherry": {
        "fg_color": "#eb3349", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#eb3349", "#f45c43"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Aqua": {
        "fg_color": "#13547a", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#13547a", "#80d0c7"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Mango": {
        "fg_color": "#ffe259", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#ffe259", "#ffa751"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Grape": {
        "fg_color": "#5b247a", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#5b247a", "#1bcedf"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Lush": {
        "fg_color": "#56ab2f", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#56ab2f", "#a8e063"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Velvet": {
        "fg_color": "#DA4453", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#DA4453", "#89216B"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Gradient Cosmic": {
        "fg_color": "#ff00cc", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "horizontal_gradient", "gradient_colors": ("#ff00cc", "#333399"),
        "drawers": ["square", "rounded", "circle"]
    },
    
    # RADIAL GRADIENTS
    "Radial Fire": {
        "fg_color": "#ff416c", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "radial_gradient", "gradient_colors": ("#ff416c", "#ff4b2b"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Radial Sunset": {
        "fg_color": "#f5576c", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "radial_gradient", "gradient_colors": ("#f5576c", "#f093fb"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Radial Ocean": {
        "fg_color": "#0052D4", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "radial_gradient", "gradient_colors": ("#0052D4", "#6FB1FC"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Radial Earth": {
        "fg_color": "#403B4A", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "radial_gradient", "gradient_colors": ("#403B4A", "#E7E9BB"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Radial Neon": {
        "fg_color": "#00F260", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "radial_gradient", "gradient_colors": ("#00F260", "#0575E6"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Radial Berry": {
        "fg_color": "#8E2DE2", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "radial_gradient", "gradient_colors": ("#8E2DE2", "#4A00E0"),
        "drawers": ["square", "rounded", "circle"]
    },
    
    # VERTICAL GRADIENTS
    "Vertical Sky": {
        "fg_color": "#2980B9", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "vertical_gradient", "gradient_colors": ("#2980B9", "#6DD5FA"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Vertical Dusk": {
        "fg_color": "#2c3e50", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "vertical_gradient", "gradient_colors": ("#2c3e50", "#bdc3c7"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Vertical Spring": {
        "fg_color": "#00b09b", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "vertical_gradient", "gradient_colors": ("#00b09b", "#96c93d"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Vertical Twilight": {
        "fg_color": "#0f0c29", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "vertical_gradient", "gradient_colors": ("#0f0c29", "#302b63"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Vertical Sunrise": {
        "fg_color": "#ff512f", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "vertical_gradient", "gradient_colors": ("#ff512f", "#f09819"),
        "drawers": ["square", "rounded", "circle"]
    },
    "Vertical Lavender": {
        "fg_color": "#834d9b", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "vertical_gradient", "gradient_colors": ("#834d9b", "#d04ed6"),
        "drawers": ["square", "rounded", "circle"]
    },
    
    # NEON
    "Neon Pink": {
        "fg_color": "#ff006e", "bg_color": "#0a0a0f", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Neon Cyan": {
        "fg_color": "#00f5d4", "bg_color": "#0a0a0f", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Neon Green": {
        "fg_color": "#39ff14", "bg_color": "#0a0a0f", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Neon Purple": {
        "fg_color": "#bf00ff", "bg_color": "#0a0a0f", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Neon Orange": {
        "fg_color": "#ff9500", "bg_color": "#0a0a0f", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Neon Yellow": {
        "fg_color": "#fff01f", "bg_color": "#0a0a0f", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Neon Red": {
        "fg_color": "#ff073a", "bg_color": "#0a0a0f", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Neon Blue": {
        "fg_color": "#00b4ff", "bg_color": "#0a0a0f", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    
    # RETRO
    "Retro Terminal": {
        "fg_color": "#00ff41", "bg_color": "#0d0208", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "gapped"]
    },
    "Retro Amber": {
        "fg_color": "#ffb000", "bg_color": "#1a1100", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "gapped"]
    },
    "Retro Blue CRT": {
        "fg_color": "#00b4d8", "bg_color": "#03071e", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "gapped"]
    },
    "Retro Sepia": {
        "fg_color": "#704214", "bg_color": "#f5e6c8", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "gapped"]
    },
    "Retro Cream": {
        "fg_color": "#5c4033", "bg_color": "#fffdd0", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "gapped"]
    },
    
    # ELEGANT
    "Elegant Gold": {
        "fg_color": "#d4af37", "bg_color": "#1a1a1a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Elegant Silver": {
        "fg_color": "#c0c0c0", "bg_color": "#1a1a1a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Elegant Rose Gold": {
        "fg_color": "#b76e79", "bg_color": "#1a1a1a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Elegant Bronze": {
        "fg_color": "#cd7f32", "bg_color": "#1a1a1a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Elegant Platinum": {
        "fg_color": "#e5e4e2", "bg_color": "#1a1a1a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Elegant Copper": {
        "fg_color": "#b87333", "bg_color": "#1a1a1a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Elegant Champagne": {
        "fg_color": "#f7e7ce", "bg_color": "#2d2d2d", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    
    # SOFT/PASTEL
    "Soft Purple": {
        "fg_color": "#a78bfa", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Soft Blue": {
        "fg_color": "#93c5fd", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Soft Pink": {
        "fg_color": "#f9a8d4", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Soft Mint": {
        "fg_color": "#6ee7b7", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Soft Coral": {
        "fg_color": "#fca5a5", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Soft Lavender": {
        "fg_color": "#c4b5fd", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Soft Peach": {
        "fg_color": "#fdba74", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Soft Sky": {
        "fg_color": "#7dd3fc", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Soft Rose": {
        "fg_color": "#fda4af", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    "Soft Lime": {
        "fg_color": "#bef264", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle"]
    },
    
    # DARK MODE
    "Dark Slate": {
        "fg_color": "#94a3b8", "bg_color": "#0f172a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Dark Teal": {
        "fg_color": "#2dd4bf", "bg_color": "#0f172a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Dark Berry": {
        "fg_color": "#f472b6", "bg_color": "#0f172a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Dark Sky": {
        "fg_color": "#38bdf8", "bg_color": "#0f172a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Dark Amber": {
        "fg_color": "#fbbf24", "bg_color": "#0f172a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Dark Emerald": {
        "fg_color": "#34d399", "bg_color": "#0f172a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Dark Violet": {
        "fg_color": "#a78bfa", "bg_color": "#0f172a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Dark Rose": {
        "fg_color": "#fb7185", "bg_color": "#0f172a", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    
    # VIBRANT
    "Vibrant Red": {
        "fg_color": "#ef4444", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Vibrant Blue": {
        "fg_color": "#3b82f6", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Vibrant Green": {
        "fg_color": "#22c55e", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Vibrant Yellow": {
        "fg_color": "#eab308", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Vibrant Purple": {
        "fg_color": "#8b5cf6", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Vibrant Orange": {
        "fg_color": "#f97316", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Vibrant Cyan": {
        "fg_color": "#06b6d4", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
    "Vibrant Fuchsia": {
        "fg_color": "#d946ef", "bg_color": "#FFFFFF", "transparent": False,
        "color_mask": "solid", "gradient_colors": None,
        "drawers": ["square", "rounded", "circle", "gapped"]
    },
}


# =============================================================================
# CACHED QR GENERATION FOR PERFORMANCE
# =============================================================================
@lru_cache(maxsize=512)
def generate_cached_qr_data(data, box_size, border):
    """Generate and cache QR matrix data."""
    qr = qrcode.QRCode(version=1, error_correction=ERROR_CORRECT_M, box_size=box_size, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    return qr


# =============================================================================
# MAIN APPLICATION CLASS
# =============================================================================
class QRCodeGeneratorPro:
    """Professional QR Code Generator with Visual Style Gallery."""
    
    APP_THEMES = {
        "Dark": {
            "bg": "#1a1a2e", "fg": "#eaeaea", "accent": "#7c3aed",
            "button_bg": "#2d2d44", "button_fg": "#eaeaea",
            "entry_bg": "#2d2d44", "entry_fg": "#eaeaea",
            "frame_bg": "#16162a", "highlight": "#3d3d5c",
            "success": "#22c55e", "error": "#ef4444", "warning": "#f59e0b",
            "menu_bg": "#2d2d44", "menu_fg": "#eaeaea",
            "card_bg": "#232340", "selected": "#7c3aed"
        },
        "Light": {
            "bg": "#f8fafc", "fg": "#1e293b", "accent": "#6366f1",
            "button_bg": "#e2e8f0", "button_fg": "#1e293b",
            "entry_bg": "#ffffff", "entry_fg": "#1e293b",
            "frame_bg": "#f1f5f9", "highlight": "#cbd5e1",
            "success": "#16a34a", "error": "#dc2626", "warning": "#d97706",
            "menu_bg": "#f1f5f9", "menu_fg": "#1e293b",
            "card_bg": "#ffffff", "selected": "#6366f1"
        },
        "Nord": {
            "bg": "#2e3440", "fg": "#eceff4", "accent": "#88c0d0",
            "button_bg": "#3b4252", "button_fg": "#eceff4",
            "entry_bg": "#3b4252", "entry_fg": "#eceff4",
            "frame_bg": "#272c36", "highlight": "#4c566a",
            "success": "#a3be8c", "error": "#bf616a", "warning": "#ebcb8b",
            "menu_bg": "#3b4252", "menu_fg": "#eceff4",
            "card_bg": "#3b4252", "selected": "#88c0d0"
        },
    }
    
    # Gallery background presets
    GALLERY_BG_PRESETS = {
        "Transparent": None,
        "White": "#FFFFFF",
        "Light Gray": "#E5E5E5",
        "Dark Gray": "#333333",
        "Black": "#000000",
        "Custom...": "custom"
    }
    
    ERROR_CORRECTION = {
        "Low (7%)": ERROR_CORRECT_L,
        "Medium (15%)": ERROR_CORRECT_M,
        "Quartile (25%)": ERROR_CORRECT_Q,
        "High (30%)": ERROR_CORRECT_H
    }
    
    DEBOUNCE_DELAY = 250  # Faster response
    
    # Zoom settings - DEFAULT 160%
    GALLERY_ZOOM_MIN = 60
    GALLERY_ZOOM_MAX = 200
    GALLERY_ZOOM_DEFAULT = 160
    
    PREVIEW_ZOOM_MIN = 50
    PREVIEW_ZOOM_MAX = 100
    PREVIEW_ZOOM_DEFAULT = 90
    
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        
        # Fullscreen
        if platform.system() == "Windows":
            self.root.state('zoomed')
        else:
            try:
                self.root.attributes('-zoomed', True)
            except:
                self.root.geometry("1400x900")
        
        self.root.minsize(1200, 800)
        
        # State
        self.current_theme = "Dark"
        self.qr_image = None
        self.qr_pil_image = None
        self.fg_color = "#000000"
        self.bg_color = "#FFFFFF"
        self.debounce_timer = None
        self.last_generated_data = None
        self.preview_images = {}
        self.selected_preset_key = None
        self.preset_frames = {}
        self.current_gradient_config = None
        self.gallery_loading = False
        
        # Gallery background color (None = transparent/checkerboard)
        self.gallery_bg_color = None
        
        # Zoom variables
        self.gallery_zoom = tk.IntVar(value=self.GALLERY_ZOOM_DEFAULT)
        self.preview_zoom = tk.IntVar(value=self.PREVIEW_ZOOM_DEFAULT)
        
        # Default transparent - ALWAYS ON
        self.transparent_var = tk.BooleanVar(value=True)
        
        # Thread pool for background generation
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Pre-generate checkerboard patterns (performance optimization)
        self._checkerboard_cache = {}
        
        # Setup
        self.setup_styles()
        self.create_menu_bar()
        self.create_widgets()
        self.apply_theme()
        self.bind_shortcuts()
        self.update_button_states()
        
        # Bind resize event
        self._resize_timer = None
        self.root.bind("<Configure>", self.on_window_configure)
        
        # Load gallery after UI ready
        self.root.after(50, self.start_gallery_generation)
        
        logger.info("Application initialized")
    
    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
    
    def bind_shortcuts(self):
        self.root.bind("<Control-n>", lambda e: self.new_qr())
        self.root.bind("<Control-N>", lambda e: self.new_qr())
        self.root.bind("<Control-g>", lambda e: self.generate_qr())
        self.root.bind("<Control-G>", lambda e: self.generate_qr())
        self.root.bind("<Control-s>", lambda e: self.save_qr())
        self.root.bind("<Control-S>", lambda e: self.save_qr())
        self.root.bind("<Control-c>", lambda e: self.copy_qr())
        self.root.bind("<Control-C>", lambda e: self.copy_qr())
        self.root.bind("<Control-Shift-c>", lambda e: self.copy_data())
        self.root.bind("<Control-Shift-C>", lambda e: self.copy_data())
        self.root.bind("<Control-v>", lambda e: self.paste_data())
        self.root.bind("<Control-V>", lambda e: self.paste_data())
        self.root.bind("<F1>", lambda e: self.show_help())
        self.root.bind("<F5>", lambda e: self.generate_qr())
        self.root.bind("<Control-q>", lambda e: self.quit_app())
        self.root.bind("<Control-Q>", lambda e: self.quit_app())
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Control-plus>", lambda e: self.zoom_gallery(20))
        self.root.bind("<Control-equal>", lambda e: self.zoom_gallery(20))
        self.root.bind("<Control-minus>", lambda e: self.zoom_gallery(-20))
    
    def create_menu_bar(self):
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="New", command=self.new_qr, accelerator="Ctrl+N")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Save", command=self.save_qr, accelerator="Ctrl+S")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.quit_app, accelerator="Ctrl+Q")
        
        self.edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Edit", menu=self.edit_menu)
        self.edit_menu.add_command(label="Paste Data", command=self.paste_data, accelerator="Ctrl+V")
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Copy Image", command=self.copy_qr, accelerator="Ctrl+C")
        self.edit_menu.add_command(label="Copy Data", command=self.copy_data, accelerator="Ctrl+Shift+C")
        
        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="View", menu=self.view_menu)
        
        self.theme_menu = tk.Menu(self.view_menu, tearoff=0)
        self.view_menu.add_cascade(label="Theme", menu=self.theme_menu)
        self.theme_var_menu = tk.StringVar(value=self.current_theme)
        for name in self.APP_THEMES:
            self.theme_menu.add_radiobutton(label=name, variable=self.theme_var_menu,
                value=name, command=self.on_menu_theme_change)
        
        self.view_menu.add_separator()
        self.view_menu.add_command(label="Zoom In Gallery", command=lambda: self.zoom_gallery(20), accelerator="Ctrl++")
        self.view_menu.add_command(label="Zoom Out Gallery", command=lambda: self.zoom_gallery(-20), accelerator="Ctrl+-")
        self.view_menu.add_command(label="Reset Zoom", command=self.reset_gallery_zoom)
        self.view_menu.add_separator()
        self.view_menu.add_command(label="Toggle Fullscreen", command=self.toggle_fullscreen, accelerator="F11")
        
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="Help", command=self.show_help, accelerator="F1")
        self.help_menu.add_command(label="Shortcuts", command=self.show_shortcuts)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="About", command=self.show_about)
    
    def toggle_fullscreen(self):
        if platform.system() == "Windows":
            self.root.state('normal' if self.root.state() == 'zoomed' else 'zoomed')
        else:
            current = self.root.attributes('-zoomed')
            self.root.attributes('-zoomed', not current)
    
    def apply_theme(self):
        theme = self.APP_THEMES[self.current_theme]
        self.root.configure(bg=theme["bg"])
        
        self.style.configure("TFrame", background=theme["bg"])
        self.style.configure("Card.TFrame", background=theme["frame_bg"])
        self.style.configure("Gallery.TFrame", background=theme["bg"])
        
        self.style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
        self.style.configure("Card.TLabel", background=theme["frame_bg"], foreground=theme["fg"])
        self.style.configure("Title.TLabel", background=theme["bg"], foreground=theme["accent"],
                           font=("Segoe UI", 16, "bold"))
        self.style.configure("Subtitle.TLabel", background=theme["frame_bg"], foreground=theme["fg"],
                           font=("Segoe UI", 11, "bold"))
        self.style.configure("FamilyTitle.TLabel", background=theme["bg"], foreground=theme["accent"],
                           font=("Segoe UI", 11, "bold"))
        self.style.configure("Status.TLabel", background=theme["bg"], foreground=theme["fg"])
        self.style.configure("Success.TLabel", background=theme["bg"], foreground=theme["success"])
        self.style.configure("Valid.TLabel", background=theme["frame_bg"], foreground=theme["success"])
        self.style.configure("Invalid.TLabel", background=theme["frame_bg"], foreground=theme["error"])
        self.style.configure("Zoom.TLabel", background=theme["bg"], foreground=theme["fg"], font=("Segoe UI", 9))
        
        self.style.configure("TButton", background=theme["button_bg"], foreground=theme["button_fg"],
                           font=("Segoe UI", 10), padding=(6, 3))
        self.style.map("TButton", background=[("active", theme["accent"]), ("disabled", theme["highlight"])],
                      foreground=[("active", theme["bg"]), ("disabled", theme["highlight"])])
        
        self.style.configure("Accent.TButton", background=theme["accent"], foreground="#ffffff",
                           font=("Segoe UI", 10, "bold"), padding=(10, 5))
        self.style.map("Accent.TButton", background=[("active", theme["success"]), ("disabled", theme["highlight"])])
        
        self.style.configure("TEntry", fieldbackground=theme["entry_bg"], foreground=theme["entry_fg"])
        self.style.configure("TCombobox", fieldbackground=theme["entry_bg"], foreground=theme["entry_fg"])
        self.style.map("TCombobox", fieldbackground=[("readonly", theme["entry_bg"])])
        
        self.style.configure("TRadiobutton", background=theme["frame_bg"], foreground=theme["fg"])
        self.style.configure("TCheckbutton", background=theme["frame_bg"], foreground=theme["fg"])
        self.style.configure("TScale", background=theme["bg"], troughcolor=theme["highlight"])
        
        for menu in [self.file_menu, self.edit_menu, self.view_menu, self.help_menu, self.theme_menu]:
            menu.configure(bg=theme["menu_bg"], fg=theme["menu_fg"],
                          activebackground=theme["accent"], activeforeground="#ffffff")
        
        if hasattr(self, 'preview_canvas'):
            self.preview_canvas.configure(bg=theme["frame_bg"], highlightbackground=theme["highlight"])
        if hasattr(self, 'gallery_canvas'):
            self.gallery_canvas.configure(bg=theme["bg"])
        if hasattr(self, 'fg_preview'):
            self.fg_preview.configure(highlightbackground=theme["highlight"])
            self.bg_preview.configure(highlightbackground=theme["highlight"])
    
    def create_widgets(self):
        theme = self.APP_THEMES[self.current_theme]
        
        # Main horizontal paned window
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # =====================================================================
        # LEFT PANEL - Input & Gallery
        # =====================================================================
        left_panel = ttk.Frame(self.main_paned)
        self.main_paned.add(left_panel, weight=3)
        
        # Header
        header = ttk.Frame(left_panel)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text=f"📱 {APP_NAME}", style="Title.TLabel").pack(side=tk.LEFT)
        
        hdr_right = ttk.Frame(header)
        hdr_right.pack(side=tk.RIGHT)
        ttk.Label(hdr_right, text="Theme:").pack(side=tk.LEFT, padx=(0, 5))
        self.theme_var = tk.StringVar(value=self.current_theme)
        ttk.Combobox(hdr_right, textvariable=self.theme_var, values=list(self.APP_THEMES.keys()),
                    state="readonly", width=8).pack(side=tk.LEFT)
        self.theme_var.trace_add("write", lambda *_: self.on_theme_change())
        
        # Input card (compact)
        input_card = ttk.Frame(left_panel, style="Card.TFrame", padding=8)
        input_card.pack(fill=tk.X, pady=(0, 8))
        
        input_row = ttk.Frame(input_card, style="Card.TFrame")
        input_row.pack(fill=tk.X)
        
        self.input_type = tk.StringVar(value="url")
        for txt, val in [("🔗 URL", "url"), ("📞 Phone", "phone"), ("📝 Text", "text")]:
            ttk.Radiobutton(input_row, text=txt, variable=self.input_type, value=val,
                           command=self.on_type_change).pack(side=tk.LEFT, padx=(0, 8))
        
        self.validation_var = tk.StringVar()
        self.validation_label = ttk.Label(input_row, textvariable=self.validation_var, style="Card.TLabel")
        self.validation_label.pack(side=tk.RIGHT)
        
        self.input_var = tk.StringVar()
        self.input_var.trace_add("write", self.on_input_change)
        self.input_entry = ttk.Entry(input_card, textvariable=self.input_var, font=("Segoe UI", 11))
        self.input_entry.pack(fill=tk.X, ipady=5, pady=(6, 0))
        
        # Gallery header with controls
        gallery_hdr = ttk.Frame(left_panel)
        gallery_hdr.pack(fill=tk.X, pady=(4, 4))
        
        # Left side: Title and count
        hdr_left = ttk.Frame(gallery_hdr)
        hdr_left.pack(side=tk.LEFT)
        
        ttk.Label(hdr_left, text="Style Gallery", style="Title.TLabel",
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        
        total_presets = sum(len(f["drawers"]) for f in PRESET_FAMILIES.values())
        ttk.Label(hdr_left, text=f"({len(PRESET_FAMILIES)} families, {total_presets} styles)",
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(8, 0))
        
        # Right side: Controls
        hdr_right = ttk.Frame(gallery_hdr)
        hdr_right.pack(side=tk.RIGHT)
        
        # Background color selector
        ttk.Label(hdr_right, text="Preview BG:", style="Zoom.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self.gallery_bg_var = tk.StringVar(value="Transparent")
        bg_combo = ttk.Combobox(hdr_right, textvariable=self.gallery_bg_var,
                               values=list(self.GALLERY_BG_PRESETS.keys()),
                               state="readonly", width=12)
        bg_combo.pack(side=tk.LEFT, padx=(0, 10))
        bg_combo.bind("<<ComboboxSelected>>", self.on_gallery_bg_change)
        
        # Zoom controls
        ttk.Label(hdr_right, text="🔍", style="Zoom.TLabel").pack(side=tk.LEFT)
        ttk.Button(hdr_right, text="−", width=2, command=lambda: self.zoom_gallery(-20)).pack(side=tk.LEFT, padx=2)
        self.gallery_zoom_label = ttk.Label(hdr_right, text=f"{self.gallery_zoom.get()}%", 
                                           style="Zoom.TLabel", width=5)
        self.gallery_zoom_label.pack(side=tk.LEFT)
        ttk.Button(hdr_right, text="+", width=2, command=lambda: self.zoom_gallery(20)).pack(side=tk.LEFT, padx=2)
        
        # Gallery scrollable area
        gallery_container = ttk.Frame(left_panel)
        gallery_container.pack(fill=tk.BOTH, expand=True)
        
        self.gallery_canvas = tk.Canvas(gallery_container, bg=theme["bg"], highlightthickness=0)
        gallery_scroll = ttk.Scrollbar(gallery_container, orient=tk.VERTICAL, command=self.gallery_canvas.yview)
        
        self.gallery_frame = ttk.Frame(self.gallery_canvas, style="Gallery.TFrame")
        
        self.gallery_canvas.configure(yscrollcommand=gallery_scroll.set)
        gallery_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.gallery_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.gallery_window = self.gallery_canvas.create_window((0, 0), window=self.gallery_frame, anchor=tk.NW)
        
        self.gallery_frame.bind("<Configure>", self._on_gallery_frame_configure)
        self.gallery_canvas.bind("<Configure>", self._on_gallery_canvas_configure)
        
        # Smooth scrolling
        self.gallery_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # =====================================================================
        # RIGHT PANEL - Preview & Settings
        # =====================================================================
        right_panel = ttk.Frame(self.main_paned)
        self.main_paned.add(right_panel, weight=1)
        
        right_paned = ttk.PanedWindow(right_panel, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)
        
        # Preview Card
        preview_card = ttk.Frame(right_paned, style="Card.TFrame", padding=12)
        right_paned.add(preview_card, weight=3)
        
        preview_hdr = ttk.Frame(preview_card, style="Card.TFrame")
        preview_hdr.pack(fill=tk.X)
        
        ttk.Label(preview_hdr, text="Preview", style="Subtitle.TLabel").pack(side=tk.LEFT)
        
        pzoom_frame = ttk.Frame(preview_hdr, style="Card.TFrame")
        pzoom_frame.pack(side=tk.RIGHT)
        ttk.Label(pzoom_frame, text="Fill:", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(pzoom_frame, text="−", width=2, command=lambda: self.zoom_preview(-10)).pack(side=tk.LEFT, padx=1)
        self.preview_zoom_label = ttk.Label(pzoom_frame, text=f"{self.preview_zoom.get()}%", 
                                           style="Card.TLabel", width=5)
        self.preview_zoom_label.pack(side=tk.LEFT)
        ttk.Button(pzoom_frame, text="+", width=2, command=lambda: self.zoom_preview(10)).pack(side=tk.LEFT, padx=1)
        
        ttk.Separator(preview_card, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
        
        preview_container = ttk.Frame(preview_card, style="Card.TFrame")
        preview_container.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        self.preview_canvas = tk.Canvas(preview_container, bg=theme["frame_bg"],
                                        highlightthickness=1, highlightbackground=theme["highlight"])
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        
        self.show_preview_placeholder()
        
        self.img_info_var = tk.StringVar()
        ttk.Label(preview_card, textvariable=self.img_info_var, style="Card.TLabel").pack(anchor=tk.W, pady=(0, 6))
        
        # Buttons
        self.generate_btn = ttk.Button(preview_card, text="⚡ Generate QR Code",
                                       style="Accent.TButton", command=self.generate_qr)
        self.generate_btn.pack(fill=tk.X, pady=(0, 5))
        
        btn_row = ttk.Frame(preview_card, style="Card.TFrame")
        btn_row.pack(fill=tk.X, pady=(0, 3))
        self.save_btn = ttk.Button(btn_row, text="💾 Save", command=self.save_qr)
        self.save_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.copy_btn = ttk.Button(btn_row, text="📋 Copy", command=self.copy_qr)
        self.copy_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        
        self.copy_data_btn = ttk.Button(preview_card, text="📄 Copy Data", command=self.copy_data)
        self.copy_data_btn.pack(fill=tk.X)
        
        # Settings Card
        settings_card = ttk.Frame(right_paned, style="Card.TFrame", padding=12)
        right_paned.add(settings_card, weight=1)
        
        ttk.Label(settings_card, text="Settings", style="Subtitle.TLabel").pack(anchor=tk.W)
        ttk.Separator(settings_card, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
        
        settings_inner = ttk.Frame(settings_card, style="Card.TFrame")
        settings_inner.pack(fill=tk.BOTH, expand=True)
        
        # Colors
        colors_frame = ttk.Frame(settings_inner, style="Card.TFrame")
        colors_frame.pack(fill=tk.X, pady=(0, 6))
        
        fg_row = ttk.Frame(colors_frame, style="Card.TFrame")
        fg_row.pack(fill=tk.X, pady=2)
        ttk.Label(fg_row, text="QR Color:", style="Card.TLabel", width=10).pack(side=tk.LEFT)
        self.fg_preview = tk.Label(fg_row, bg=self.fg_color, width=3, relief=tk.SOLID, highlightthickness=1)
        self.fg_preview.pack(side=tk.LEFT, padx=(0, 4))
        self.fg_hex_var = tk.StringVar(value=self.fg_color)
        ttk.Entry(fg_row, textvariable=self.fg_hex_var, width=8, font=("Consolas", 9)).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(fg_row, text="...", width=2, command=self.choose_fg_color).pack(side=tk.LEFT)
        
        bg_row = ttk.Frame(colors_frame, style="Card.TFrame")
        bg_row.pack(fill=tk.X, pady=2)
        ttk.Label(bg_row, text="Background:", style="Card.TLabel", width=10).pack(side=tk.LEFT)
        self.bg_preview = tk.Label(bg_row, bg=self.bg_color, width=3, relief=tk.SOLID, highlightthickness=1)
        self.bg_preview.pack(side=tk.LEFT, padx=(0, 4))
        self.bg_hex_var = tk.StringVar(value=self.bg_color)
        ttk.Entry(bg_row, textvariable=self.bg_hex_var, width=8, font=("Consolas", 9)).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(bg_row, text="...", width=2, command=self.choose_bg_color).pack(side=tk.LEFT)
        
        # Transparent checkbox - ALWAYS CHECKED BY DEFAULT
        ttk.Checkbutton(colors_frame, text="Transparent Background (PNG)",
                       variable=self.transparent_var, command=self.on_setting_change).pack(anchor=tk.W, pady=(3, 0))
        
        # Shape
        shape_row = ttk.Frame(settings_inner, style="Card.TFrame")
        shape_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(shape_row, text="Shape:", style="Card.TLabel", width=10).pack(side=tk.LEFT)
        self.drawer_var = tk.StringVar(value="Square")
        ttk.Combobox(shape_row, textvariable=self.drawer_var, values=list(MODULE_DRAWER_NAMES.values()),
                    state="readonly", width=12).pack(side=tk.LEFT)
        
        # Size & Border (compact)
        size_border_row = ttk.Frame(settings_inner, style="Card.TFrame")
        size_border_row.pack(fill=tk.X, pady=(0, 6))
        
        ttk.Label(size_border_row, text="Size:", style="Card.TLabel").pack(side=tk.LEFT)
        self.size_var = tk.IntVar(value=10)
        ttk.Scale(size_border_row, from_=5, to=25, variable=self.size_var, orient=tk.HORIZONTAL,
                 length=80, command=self.on_size_change).pack(side=tk.LEFT)
        self.size_label = ttk.Label(size_border_row, text="10", style="Card.TLabel", width=2)
        self.size_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(size_border_row, text="Border:", style="Card.TLabel").pack(side=tk.LEFT)
        self.border_var = tk.IntVar(value=4)
        ttk.Scale(size_border_row, from_=0, to=10, variable=self.border_var, orient=tk.HORIZONTAL,
                 length=80, command=self.on_border_change).pack(side=tk.LEFT)
        self.border_label = ttk.Label(size_border_row, text="4", style="Card.TLabel", width=2)
        self.border_label.pack(side=tk.LEFT)
        
        # EC & Format (compact)
        ec_fmt_row = ttk.Frame(settings_inner, style="Card.TFrame")
        ec_fmt_row.pack(fill=tk.X)
        
        ttk.Label(ec_fmt_row, text="EC:", style="Card.TLabel").pack(side=tk.LEFT)
        self.ec_var = tk.StringVar(value="Medium (15%)")
        ttk.Combobox(ec_fmt_row, textvariable=self.ec_var, values=list(self.ERROR_CORRECTION.keys()),
                    state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(ec_fmt_row, text="Format:", style="Card.TLabel").pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value="PNG")
        ttk.Combobox(ec_fmt_row, textvariable=self.format_var, values=["PNG", "JPEG", "BMP", "GIF", "TIFF"],
                    state="readonly", width=8).pack(side=tk.LEFT)
        
        # Status bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.status_var = tk.StringVar(value="Loading styles...")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT)
        ttk.Label(status_frame, text=f"v{APP_VERSION}").pack(side=tk.RIGHT)
    
    def _on_gallery_frame_configure(self, event):
        self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
    
    def _on_gallery_canvas_configure(self, event):
        self.gallery_canvas.itemconfig(self.gallery_window, width=event.width)
    
    def _on_mousewheel(self, event):
        # Smoother scrolling with smaller increments
        self.gallery_canvas.yview_scroll(int(-1 * (event.delta / 60)), "units")
    
    def on_window_configure(self, event):
        if hasattr(self, 'qr_pil_image') and self.qr_pil_image:
            if self._resize_timer:
                self.root.after_cancel(self._resize_timer)
            self._resize_timer = self.root.after(50, self.update_preview)
    
    def on_gallery_bg_change(self, event=None):
        """Handle gallery background color change."""
        selection = self.gallery_bg_var.get()
        preset_value = self.GALLERY_BG_PRESETS.get(selection)
        
        if preset_value == "custom":
            # Open color picker
            color = colorchooser.askcolor(initialcolor="#FFFFFF", parent=self.root,
                                         title="Choose Gallery Background")
            if color[1]:
                self.gallery_bg_color = color[1]
            else:
                self.gallery_bg_var.set("Transparent")
                self.gallery_bg_color = None
                return
        else:
            self.gallery_bg_color = preset_value
        
        # Regenerate gallery with new background
        self.regenerate_gallery()
    
    def zoom_gallery(self, delta):
        new_zoom = self.gallery_zoom.get() + delta
        new_zoom = max(self.GALLERY_ZOOM_MIN, min(self.GALLERY_ZOOM_MAX, new_zoom))
        self.gallery_zoom.set(new_zoom)
        self.gallery_zoom_label.config(text=f"{new_zoom}%")
        self.regenerate_gallery()
    
    def reset_gallery_zoom(self):
        self.gallery_zoom.set(self.GALLERY_ZOOM_DEFAULT)
        self.gallery_zoom_label.config(text=f"{self.GALLERY_ZOOM_DEFAULT}%")
        self.regenerate_gallery()
    
    def zoom_preview(self, delta):
        new_zoom = self.preview_zoom.get() + delta
        new_zoom = max(self.PREVIEW_ZOOM_MIN, min(self.PREVIEW_ZOOM_MAX, new_zoom))
        self.preview_zoom.set(new_zoom)
        self.preview_zoom_label.config(text=f"{new_zoom}%")
        self.update_preview()
    
    def regenerate_gallery(self):
        if self.gallery_loading:
            return
        for w in self.gallery_frame.winfo_children():
            w.destroy()
        self.preset_frames.clear()
        self.preview_images.clear()
        self._checkerboard_cache.clear()
        self.root.after(10, self.start_gallery_generation)
    
    def start_gallery_generation(self):
        """Start generating gallery in batches for responsiveness."""
        self.gallery_loading = True
        self.set_status("Loading styles...")
        
        # Get all presets as list
        self.preset_list = []
        for family_name, config in PRESET_FAMILIES.items():
            for drawer_key in config["drawers"]:
                self.preset_list.append((family_name, drawer_key, config))
        
        self.current_family = None
        self.preset_index = 0
        self.gallery_row = 0
        
        # Start batch processing
        self.root.after(5, self._generate_batch)
    
    def _generate_batch(self):
        """Generate a batch of previews."""
        theme = self.APP_THEMES[self.current_theme]
        batch_size = 12  # Process 12 presets at a time
        thumb_size = self.gallery_zoom.get()
        
        for _ in range(batch_size):
            if self.preset_index >= len(self.preset_list):
                # Done
                self.gallery_loading = False
                self.set_status(f"Ready - {len(PRESET_FAMILIES)} style families")
                return
            
            family_name, drawer_key, config = self.preset_list[self.preset_index]
            
            # Check if new family
            if family_name != self.current_family:
                self.current_family = family_name
                
                # Add family header
                fam_frame = ttk.Frame(self.gallery_frame, style="Gallery.TFrame")
                fam_frame.grid(row=self.gallery_row, column=0, sticky=tk.W, pady=(12, 4), padx=5)
                ttk.Label(fam_frame, text=family_name, style="FamilyTitle.TLabel").pack(anchor=tk.W)
                self.gallery_row += 1
                
                # New presets row
                self.presets_row = ttk.Frame(self.gallery_frame, style="Gallery.TFrame")
                self.presets_row.grid(row=self.gallery_row, column=0, sticky=tk.W, padx=5)
                self.gallery_row += 1
                self.preset_col = 0
            
            # Generate preview
            preset_key = f"{family_name}|{drawer_key}"
            preview_img = self._generate_preview_fast(config, drawer_key, thumb_size)
            
            if preview_img:
                self.preview_images[preset_key] = ImageTk.PhotoImage(preview_img)
                
                # Create card
                pad = max(2, thumb_size // 40)
                card = tk.Frame(self.presets_row, bg=theme["card_bg"], padx=pad, pady=pad,
                               highlightthickness=2, highlightbackground=theme["highlight"])
                card.grid(row=0, column=self.preset_col, padx=3, pady=3)
                self.preset_frames[preset_key] = card
                
                img_lbl = tk.Label(card, image=self.preview_images[preset_key],
                                  bg=theme["card_bg"], cursor="hand2")
                img_lbl.pack()
                
                font_size = max(8, thumb_size // 14)
                name_lbl = tk.Label(card, text=MODULE_DRAWER_NAMES[drawer_key],
                                   bg=theme["card_bg"], fg=theme["fg"], 
                                   font=("Segoe UI", font_size))
                name_lbl.pack()
                
                # Bind events
                for w in [card, img_lbl, name_lbl]:
                    w.bind("<Button-1>", lambda e, pk=preset_key: self.select_preset(pk))
                    w.bind("<Enter>", lambda e, c=card: c.configure(highlightbackground=theme["accent"]))
                    w.bind("<Leave>", lambda e, c=card, pk=preset_key:
                           c.configure(highlightbackground=theme["selected"] if pk == self.selected_preset_key else theme["highlight"]))
                
                self.preset_col += 1
            
            self.preset_index += 1
        
        # Continue with next batch
        self.root.after(1, self._generate_batch)
    
    def _generate_preview_fast(self, config, drawer_key, size):
        """Optimized preview generation."""
        try:
            # Use smaller box_size for faster generation
            box_size = max(2, size // 30)
            
            qr = qrcode.QRCode(version=1, error_correction=ERROR_CORRECT_M, box_size=box_size, border=1)
            qr.add_data("https://example.com")
            qr.make(fit=True)
            
            drawer = MODULE_DRAWER_CLASSES.get(drawer_key, SquareModuleDrawer)()
            
            # All previews use transparent QR
            fg_rgb = self.hex_to_rgb(config["fg_color"])
            color_mask = SolidFillColorMask(back_color=(255, 255, 255, 0), front_color=fg_rgb + (255,))
            
            img = qr.make_image(image_factory=StyledPilImage, module_drawer=drawer,
                               color_mask=color_mask).convert('RGBA')
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Apply background
            if self.gallery_bg_color:
                # Solid color background
                bg_rgb = self.hex_to_rgb(self.gallery_bg_color)
                bg_img = Image.new('RGBA', img.size, bg_rgb + (255,))
                bg_img.paste(img, (0, 0), img)
                return bg_img
            else:
                # Checkerboard for transparency
                checker = self._get_checkerboard(img.size, max(4, size // 18))
                checker.paste(img, (0, 0), img)
                return checker
            
        except Exception as e:
            logger.error(f"Preview generation failed: {e}")
            return None
    
    def _get_checkerboard(self, size, sq):
        """Get or create cached checkerboard pattern."""
        key = (size[0], size[1], sq)
        if key not in self._checkerboard_cache:
            checker = Image.new('RGBA', size, (220, 220, 220, 255))
            draw = ImageDraw.Draw(checker)
            for y in range(0, size[1], sq):
                for x in range(0, size[0], sq):
                    if (x // sq + y // sq) % 2:
                        draw.rectangle([x, y, x + sq, y + sq], fill=(250, 250, 250, 255))
            self._checkerboard_cache[key] = checker
        return self._checkerboard_cache[key].copy()
    
    def select_preset(self, preset_key):
        theme = self.APP_THEMES[self.current_theme]
        
        if self.selected_preset_key and self.selected_preset_key in self.preset_frames:
            self.preset_frames[self.selected_preset_key].configure(highlightbackground=theme["highlight"])
        
        self.selected_preset_key = preset_key
        if preset_key in self.preset_frames:
            self.preset_frames[preset_key].configure(highlightbackground=theme["selected"])
        
        family_name, drawer_key = preset_key.split("|")
        config = PRESET_FAMILIES[family_name]
        
        self.fg_color = config["fg_color"]
        self.fg_hex_var.set(self.fg_color)
        self.fg_preview.configure(bg=self.fg_color)
        
        self.bg_color = config["bg_color"] or "#FFFFFF"
        self.bg_hex_var.set(self.bg_color)
        self.bg_preview.configure(bg=self.bg_color)
        
        # ALWAYS set transparent to True when selecting any style
        self.transparent_var.set(True)
        
        self.drawer_var.set(MODULE_DRAWER_NAMES.get(drawer_key, "Square"))
        
        self.current_gradient_config = {
            "color_mask": config["color_mask"],
            "gradient_colors": config["gradient_colors"]
        }
        
        self.set_status(f"Selected: {family_name} - {MODULE_DRAWER_NAMES[drawer_key]}")
        self.schedule_debounced_generate()
    
    def hex_to_rgb(self, hex_color):
        h = hex_color.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    
    def show_preview_placeholder(self):
        theme = self.APP_THEMES[self.current_theme]
        self.preview_canvas.delete("all")
        self.preview_canvas.update_idletasks()
        w = self.preview_canvas.winfo_width() or 400
        h = self.preview_canvas.winfo_height() or 400
        self.preview_canvas.create_text(w//2, h//2, text="QR Code Preview\nEnter data to generate",
                                        fill=theme["fg"], font=("Segoe UI", 13), justify=tk.CENTER)
    
    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================
    def on_theme_change(self, *args):
        self.current_theme = self.theme_var.get()
        self.theme_var_menu.set(self.current_theme)
        self.apply_theme()
        self.regenerate_gallery()
    
    def on_menu_theme_change(self):
        self.current_theme = self.theme_var_menu.get()
        self.theme_var.set(self.current_theme)
        self.apply_theme()
        self.regenerate_gallery()
    
    def on_type_change(self):
        self.validate_input()
        self.update_button_states()
        self.schedule_debounced_generate()
    
    def on_input_change(self, *args):
        self.validate_input()
        self.update_button_states()
        self.schedule_debounced_generate()
    
    def on_setting_change(self, *args):
        self.schedule_debounced_generate()
    
    def on_size_change(self, val):
        self.size_label.config(text=str(int(float(val))))
        self.schedule_debounced_generate()
    
    def on_border_change(self, val):
        self.border_label.config(text=str(int(float(val))))
        self.schedule_debounced_generate()
    
    def schedule_debounced_generate(self):
        if not self.is_input_valid():
            return
        if self.debounce_timer:
            self.root.after_cancel(self.debounce_timer)
        self.debounce_timer = self.root.after(self.DEBOUNCE_DELAY, self._do_generate)
    
    def _do_generate(self):
        self.debounce_timer = None
        sig = self._get_sig()
        if sig == self.last_generated_data:
            return
        self.generate_qr(show_status=False)
    
    def _get_sig(self):
        return (self.input_var.get(), self.input_type.get(), self.fg_color, self.bg_color,
                self.transparent_var.get(), self.drawer_var.get(), self.size_var.get(),
                self.border_var.get(), self.ec_var.get(), str(self.current_gradient_config))
    
    def validate_input(self):
        text = self.input_var.get().strip()
        itype = self.input_type.get()
        
        if not text:
            self.validation_var.set("")
            return False
        
        valid = True
        msg = ""
        
        if itype == "url":
            if re.match(r'^https?://\S+', text, re.IGNORECASE):
                msg = "✓"
            else:
                valid = False
                msg = "Invalid URL"
        elif itype == "phone":
            cleaned = re.sub(r'[\s\-\(\)\.]', '', text)
            if re.match(r'^\+?\d{7,15}$', cleaned):
                msg = "✓"
            else:
                valid = False
                msg = "7-15 digits"
        else:
            msg = f"✓ {len(text)} chars"
        
        self.validation_var.set(msg)
        self.validation_label.configure(style="Valid.TLabel" if valid else "Invalid.TLabel")
        return valid
    
    def is_input_valid(self):
        text = self.input_var.get().strip()
        if not text:
            return False
        itype = self.input_type.get()
        if itype == "url":
            return bool(re.match(r'^https?://\S+', text, re.IGNORECASE))
        elif itype == "phone":
            return bool(re.match(r'^\+?\d{7,15}$', re.sub(r'[\s\-\(\)\.]', '', text)))
        return True
    
    def update_button_states(self):
        valid = self.is_input_valid()
        has_qr = self.qr_pil_image is not None
        has_data = bool(self.input_var.get().strip())
        
        self.generate_btn.config(state=tk.NORMAL if valid else tk.DISABLED)
        self.save_btn.config(state=tk.NORMAL if has_qr else tk.DISABLED)
        self.copy_btn.config(state=tk.NORMAL if has_qr else tk.DISABLED)
        self.copy_data_btn.config(state=tk.NORMAL if has_data else tk.DISABLED)
    
    def set_status(self, msg, level="normal"):
        self.status_var.set(msg)
        styles = {"normal": "Status.TLabel", "success": "Success.TLabel"}
        self.status_label.configure(style=styles.get(level, "Status.TLabel"))
    
    def choose_fg_color(self):
        color = colorchooser.askcolor(initialcolor=self.fg_color, parent=self.root)
        if color[1]:
            self.fg_color = color[1].upper()
            self.fg_preview.configure(bg=self.fg_color)
            self.fg_hex_var.set(self.fg_color)
            self.current_gradient_config = None
            self.schedule_debounced_generate()
    
    def choose_bg_color(self):
        color = colorchooser.askcolor(initialcolor=self.bg_color, parent=self.root)
        if color[1]:
            self.bg_color = color[1].upper()
            self.bg_preview.configure(bg=self.bg_color)
            self.bg_hex_var.set(self.bg_color)
            self.current_gradient_config = None
            self.schedule_debounced_generate()
    
    def format_data(self):
        text = self.input_var.get().strip()
        if not text:
            return ""
        if self.input_type.get() == "phone":
            cleaned = re.sub(r'[\s\-\(\)\.]', '', text)
            if not cleaned.startswith('+'):
                cleaned = '+' + cleaned
            return f"tel:{cleaned}"
        return text
    
    # =========================================================================
    # QR GENERATION
    # =========================================================================
    def generate_qr(self, show_status=True):
        if not self.is_input_valid():
            return
        
        try:
            data = self.format_data()
            
            qr = qrcode.QRCode(
                version=None,
                error_correction=self.ERROR_CORRECTION[self.ec_var.get()],
                box_size=self.size_var.get(),
                border=self.border_var.get()
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            drawer_key = None
            for k, n in MODULE_DRAWER_NAMES.items():
                if n == self.drawer_var.get():
                    drawer_key = k
                    break
            drawer = MODULE_DRAWER_CLASSES.get(drawer_key, SquareModuleDrawer)()
            
            gc = self.current_gradient_config
            if gc and gc.get("gradient_colors"):
                color_mask = self.get_gradient_mask(gc)
            elif self.transparent_var.get():
                color_mask = SolidFillColorMask(
                    back_color=(255, 255, 255, 0),
                    front_color=self.hex_to_rgb(self.fg_color) + (255,)
                )
            else:
                color_mask = SolidFillColorMask(
                    back_color=self.hex_to_rgb(self.bg_color),
                    front_color=self.hex_to_rgb(self.fg_color)
                )
            
            self.qr_pil_image = qr.make_image(
                image_factory=StyledPilImage,
                module_drawer=drawer,
                color_mask=color_mask
            ).convert('RGBA')
            
            self.last_generated_data = self._get_sig()
            self.update_preview()
            
            size = self.qr_pil_image.size
            mode = "Transparent" if self.transparent_var.get() else "Solid"
            self.img_info_var.set(f"📐 {size[0]}×{size[1]} px  |  🎨 {mode}")
            
            self.update_button_states()
            if show_status:
                self.set_status("Generated", "success")
            
        except Exception as e:
            logger.error(f"Generation error: {e}", exc_info=True)
    
    def get_gradient_mask(self, gc):
        colors = gc["gradient_colors"]
        c1 = self.hex_to_rgb(colors[0])
        c2 = self.hex_to_rgb(colors[1])
        bg = self.hex_to_rgb(self.bg_color) if not self.transparent_var.get() else (255, 255, 255)
        
        mask_type = gc["color_mask"]
        if mask_type == "horizontal_gradient":
            return HorizontalGradiantColorMask(back_color=bg, left_color=c1, right_color=c2)
        elif mask_type == "vertical_gradient":
            return VerticalGradiantColorMask(back_color=bg, top_color=c1, bottom_color=c2)
        elif mask_type == "radial_gradient":
            return RadialGradiantColorMask(back_color=bg, center_color=c1, edge_color=c2)
        elif mask_type == "square_gradient":
            return SquareGradiantColorMask(back_color=bg, center_color=c1, edge_color=c2)
        return SolidFillColorMask()
    
    def update_preview(self):
        if not self.qr_pil_image:
            return
        
        self.preview_canvas.delete("all")
        self.preview_canvas.update_idletasks()
        
        canvas_w = self.preview_canvas.winfo_width()
        canvas_h = self.preview_canvas.winfo_height()
        
        if canvas_w < 10 or canvas_h < 10:
            return
        
        zoom_pct = self.preview_zoom.get() / 100.0
        max_size = int(min(canvas_w, canvas_h) * zoom_pct)
        
        img = self.qr_pil_image.copy()
        scale = min(max_size / img.width, max_size / img.height)
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        
        if new_w > 0 and new_h > 0:
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        if img.mode == 'RGBA':
            checker_size = max(8, new_w // 25)
            checker = self._get_checkerboard(img.size, checker_size)
            checker.paste(img, (0, 0), img)
            img = checker
        
        x = (canvas_w - img.width) // 2
        y = (canvas_h - img.height) // 2
        
        self.qr_image = ImageTk.PhotoImage(img)
        self.preview_canvas.create_image(x, y, anchor=tk.NW, image=self.qr_image)
    
    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================
    def new_qr(self):
        self.input_var.set("")
        self.qr_pil_image = None
        self.qr_image = None
        self.last_generated_data = None
        self.preview_canvas.delete("all")
        self.show_preview_placeholder()
        self.img_info_var.set("")
        self.update_button_states()
        self.set_status("Ready")
    
    def save_qr(self):
        if not self.qr_pil_image:
            return
        
        fmt = self.format_var.get()
        exts = {"PNG": ".png", "JPEG": ".jpg", "BMP": ".bmp", "GIF": ".gif", "TIFF": ".tiff"}
        ext = exts.get(fmt, ".png")
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(f"{fmt} files", f"*{ext}"), ("All", "*.*")],
            initialfile=f"qrcode_{ts}{ext}",
            parent=self.root
        )
        
        if filepath:
            try:
                if fmt == "PNG":
                    self.qr_pil_image.save(filepath, "PNG")
                else:
                    rgb = Image.new('RGB', self.qr_pil_image.size, (255, 255, 255))
                    if self.qr_pil_image.mode == 'RGBA':
                        rgb.paste(self.qr_pil_image, mask=self.qr_pil_image.split()[3])
                    rgb.save(filepath, fmt, quality=95 if fmt == "JPEG" else None)
                self.set_status(f"Saved: {os.path.basename(filepath)}", "success")
            except Exception as e:
                logger.error(f"Save error: {e}")
    
    def copy_qr(self):
        if not self.qr_pil_image:
            return
        try:
            import io
            import win32clipboard
            
            output = io.BytesIO()
            rgb = Image.new('RGB', self.qr_pil_image.size, (255, 255, 255))
            if self.qr_pil_image.mode == 'RGBA':
                rgb.paste(self.qr_pil_image, mask=self.qr_pil_image.split()[3])
            rgb.save(output, 'BMP')
            
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, output.getvalue()[14:])
            win32clipboard.CloseClipboard()
            self.set_status("Copied to clipboard", "success")
        except ImportError:
            self.set_status("Install pywin32 for clipboard")
        except Exception as e:
            logger.error(f"Copy error: {e}")
    
    def copy_data(self):
        data = self.format_data()
        if data:
            self.root.clipboard_clear()
            self.root.clipboard_append(data)
            self.set_status("Data copied", "success")
    
    def paste_data(self):
        try:
            self.input_var.set(self.root.clipboard_get().strip())
        except:
            pass
    
    def quit_app(self):
        logger.info("Closing")
        self.executor.shutdown(wait=False)
        self.root.quit()
    
    # =========================================================================
    # HELP
    # =========================================================================
    def show_help(self):
        self._dialog("Help", f"""{APP_NAME}

QUICK START
1. Enter URL, phone, or text
2. Browse Style Gallery
3. Click any style to apply
4. QR generates automatically

GALLERY CONTROLS
• Preview BG: Change background color
  to preview styles on different surfaces
• Zoom +/−: Resize style previews
• Default zoom: 160%

ALL STYLES ARE TRANSPARENT
When you select any style, the output
QR code is transparent by default.

KEYBOARD SHORTCUTS
Ctrl+G/F5 - Generate
Ctrl+S - Save
Ctrl+C - Copy Image
Ctrl++/− - Zoom Gallery""", 380, 400)
    
    def show_shortcuts(self):
        self._dialog("Shortcuts", """KEYBOARD SHORTCUTS

FILE
  Ctrl+N    New
  Ctrl+S    Save
  Ctrl+Q    Exit

EDIT
  Ctrl+V    Paste Data
  Ctrl+C    Copy Image
  Ctrl+Shift+C  Copy Data

VIEW
  Ctrl++    Zoom In Gallery
  Ctrl+−    Zoom Out Gallery
  F11       Toggle Fullscreen

GENERATE
  Ctrl+G / F5   Generate QR

HELP
  F1        Help""", 260, 320)
    
    def show_about(self):
        total = sum(len(f["drawers"]) for f in PRESET_FAMILIES.values())
        self._dialog("About", f"""{APP_NAME}
Version {APP_VERSION}

{APP_COPYRIGHT}

Style Library:
• {len(PRESET_FAMILIES)} preset families
• {total} style variations

Default: 160% zoom, transparent output

MIT License""", 280, 240)
    
    def _dialog(self, title, text, w, h):
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.geometry(f"{w}x{h}")
        dlg.transient(self.root)
        dlg.grab_set()
        
        theme = self.APP_THEMES[self.current_theme]
        dlg.configure(bg=theme["frame_bg"])
        
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dlg.geometry(f"+{x}+{y}")
        
        txt = tk.Text(dlg, wrap=tk.WORD, font=("Segoe UI", 10), bg=theme["frame_bg"],
                     fg=theme["fg"], relief=tk.FLAT, padx=15, pady=15)
        txt.insert("1.0", text)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=8)
        dlg.bind("<Escape>", lambda e: dlg.destroy())


# =============================================================================
# ENTRY POINT
# =============================================================================
def main():
    root = tk.Tk()
    app = QRCodeGeneratorPro(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (logger.info("Closing"), app.executor.shutdown(wait=False), root.destroy()))
    root.mainloop()

if __name__ == "__main__":
    main()
