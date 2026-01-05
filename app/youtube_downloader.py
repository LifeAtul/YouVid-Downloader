# youtube_downloader.py
"""
Modern YouTube Downloader (CustomTkinter)
Features:
 - Modern dark "Spotify-like" black UI
 - Single, Batch, Playlist tabs
 - Real progress parsing
 - No blank terminal windows (Windows CREATE_NO_WINDOW)
 - Auto-update yt-dlp (safe tmp dir)
 - Robust path detection for PyInstaller onefile
"""

import os
import sys
import json
import subprocess
import threading
import re
import shutil
import time
from pathlib import Path
import queue

import requests
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# ---------------------------
# Path setup (robust for PyInstaller)
# ---------------------------
if getattr(sys, "frozen", False):
    # EXE running: real_base is the folder where the EXE is located
    REAL_BASE = os.path.dirname(sys.executable)
    BASE_DIR = sys._MEIPASS  # extracted resources dir
else:
    # Running as script: real_base is parent of app folder
    REAL_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RES_DIR = os.path.join(BASE_DIR, "resources")
ICON_PATH = os.path.join(RES_DIR, "icon.ico")

def get_tool_path(rel_path):
    # 1. Try bundled path (sys._MEIPASS)
    bundled = os.path.join(BASE_DIR, rel_path)
    if os.path.exists(bundled):
        return bundled
    # 2. Fallback to external path (next to EXE)
    external = os.path.join(REAL_BASE, rel_path)
    return external

YTDLP = get_tool_path(os.path.join("ytdlp", "yt-dlp.exe"))
FFMPEG = get_tool_path(os.path.join("ffmpeg", "ffmpeg.exe"))

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# ---------------------------
# Defaults / Config
# ---------------------------
DEFAULT_DOWNLOAD = r"C:\Users\Dell\Downloads"
DEFAULT_CONFIG = {
    "download_folder": DEFAULT_DOWNLOAD,
    "theme": "dark",
    "auto_open_folder": True,
    "auto_update_ytdlp": True,
    "audio_format": "m4a",
    "last_checked": None,
    "app_icon": ICON_PATH
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k,v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

cfg = load_config()

# ---------------------------
# Auto-update (safe tmp folder)
# ---------------------------
GITHUB_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"

def update_ytdlp(progress_cb):
    try:
        r = requests.get(GITHUB_API, timeout=12)
        r.raise_for_status()
        data = r.json()
        tag = data.get("tag_name", "")
        assets = data.get("assets", [])
        exe_url = None
        for a in assets:
            if a["name"].endswith("yt-dlp.exe"):
                exe_url = a["browser_download_url"]
                break
        if not exe_url:
            return False, "No yt-dlp.exe found in release."

        if cfg.get("last_checked") == tag:
            return False, f"Already {tag}"

        # ensure temp folder
        tmpfolder = os.path.join(os.getenv("TEMP"), "ytdlp")
        os.makedirs(tmpfolder, exist_ok=True)
        tmpfile = os.path.join(tmpfolder, "yt-dlp.tmp")

        progress_cb("Downloading latest yt-dlp...")
        with requests.get(exe_url, stream=True, timeout=30) as ds:
            ds.raise_for_status()
            total = int(ds.headers.get("content-length", 0) or 0)
            downloaded = 0
            with open(tmpfile, "wb") as out:
                for chunk in ds.iter_content(8192):
                    if chunk:
                        out.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded/total*100
                            progress_cb(f"Downloading: {pct:.1f}%")
        # move into place
        dst = YTDLP
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            shutil.copy2(dst, dst + ".bak")
        shutil.move(tmpfile, dst)
        os.chmod(dst, 0o755)
        cfg["last_checked"] = tag
        save_config(cfg)
        return True, f"Updated to {tag}"
    except Exception as e:
        return False, str(e)
        
# ---------------------------
# UI: Centralized Styling ("BankSafe Premium")
# ---------------------------
# Format: "key": (light_color, dark_color)
STYLES = {
    "bg": ("#f0f9ff", "#020617"),        # Sky-50 / Slate-950 (Main BG)
    "card": ("#ffffff", "#0a0f1c"),      # White / Deep Navy (Card BG) - Less Grey, More Blue/Black
    "text": ("#0c4a6e", "#f0f9ff"),      # Sky-900 / Sky-50
    "text_sub": ("#64748b", "#94a3b8"),  # Slate-500 / Slate-400
    "accent": ("#0ea5e9", "#38bdf8"),    # Sky-500 / Sky-400 (BankSafe Blue)
    "hover": ("#0284c7", "#0ea5e9"),     # Sky-600 / Sky-500
    "second": ("#e0f2fe", "#111827"),    # Sky-100 / Deep Blue (Inputs) - Replaces Grey
    "border": ("#bae6fd", "#1e293b"),    # Sky-200 / Dark Blue Border
    "success": ("#16a34a", "#22c55e"),   # Green
    "error": ("#ef4444", "#ef4444"),     # Red
}

# Fonts
MAIN_FONT = "Google Sans Code"
FONTS = {
    "header": (MAIN_FONT, 28, "bold"),
    "sub": (MAIN_FONT, 13),
    "body": (MAIN_FONT, 14),
    "bold": (MAIN_FONT, 14, "bold"),
    "mono": ("Consolas", 12)
}

# ---------------------------
# Helpers: Gradient & Process
# ---------------------------
PERC_RE = re.compile(r"(\d{1,3}\.\d+)%")

def create_gradient(w, h, c1_light, c2_light, c1_dark, c2_dark):
    """Create a vertical gradient image that works for both Light and Dark modes."""
    # Light Mode Gradient
    base_l = Image.new('RGB', (w, h), c1_light)
    top_l = Image.new('RGB', (w, h), c2_light)
    mask = Image.new('L', (w, h))
    mask_data = []
    for y in range(h):
        mask_data.extend([int(255 * (y / h))] * w)
    mask.putdata(mask_data)
    base_l.paste(top_l, (0, 0), mask)
    
    # Dark Mode Gradient
    base_d = Image.new('RGB', (w, h), c1_dark)
    top_d = Image.new('RGB', (w, h), c2_dark)
    base_d.paste(top_d, (0, 0), mask)

    return ctk.CTkImage(light_image=base_l, dark_image=base_d, size=(w, h))

class DownloadManager:
    def __init__(self):
        self.process = None
        self.cancelled = False

    def start(self, cmd, line_callback=None):
        self.cancelled = False
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        
        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                            text=True, bufsize=1, creationflags=creationflags)
            
            while True:
                if self.cancelled:
                    self.process.kill()
                    return -1, "Cancelled"
                
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                if line:
                    if line_callback:
                        line_callback(line)
            
            rc = self.process.poll()
            return rc, "Done"
        except Exception as e:
            return 1, str(e)
        finally:
            self.process = None

    def cancel(self):
        self.cancelled = True
        if self.process:
            try:
                self.process.kill()
            except:
                pass

def run_process_stream(cmd, line_callback=None):
    """Run subprocess and stream stdout lines. Hide a console on Windows for subprocesses."""
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         bufsize=1, creationflags=creationflags)
    combined = []
    while True:
        line = p.stdout.readline()
        if not line and p.poll() is not None:
            break
        if line:
            combined.append(line)
            if line_callback:
                try:
                    line_callback(line)
                except Exception:
                    pass
    rc = p.wait()
    return rc, "".join(combined)

# ---------------------------
# Worker queue for UI safe updates
# ---------------------------
ui_queue = queue.Queue()

def enqueue_ui(fn, *a, **kw):
    ui_queue.put((fn, a, kw))

# ---------------------------
# Main App Class
# ---------------------------
class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Downloader")
        self.geometry("1000x720")
        self.minsize(900, 600)
        
        # Apply initial theme
        ctk.set_appearance_mode("Dark")
        
        # 1. Gradient Background (Dynamic Light/Dark)
        # Light: Soft Blue (#eff6ff) -> White (#ffffff)
        # Dark:  Deep Navy (#1e1b4b) -> Black (#020617)
        self.grad_img = create_gradient(3000, 2000, "#eff6ff", "#ffffff", "#1e1b4b", "#020617")
        self.bg_label = ctk.CTkLabel(self, text="", image=self.grad_img)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        
        # set icon if available
        try:
            self.iconbitmap(cfg.get("app_icon", ICON_PATH))
        except Exception:
            pass

        # --- Header ---
        # fg_color="transparent" to show gradient
        header = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0, height=80)
        header.pack(fill="x", padx=24, pady=(24, 16))
        
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")
        
        ctk.CTkLabel(title_frame, text="YouTube Downloader", font=FONTS["header"], text_color=STYLES["text"]).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Premium Video & Audio Downloader", font=FONTS["sub"], text_color=STYLES["text_sub"]).pack(anchor="w")

        # Header Buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")
        
        # Theme Toggle
        self.theme_switch = ctk.CTkSwitch(btn_frame, text="Dark Mode", command=self.toggle_theme, 
                                          onvalue="dark", offvalue="light", 
                                          progress_color=STYLES["accent"], button_color=STYLES["text"],
                                          button_hover_color=STYLES["text_sub"],
                                          text_color=STYLES["text"], font=FONTS["sub"])
        self.theme_switch.select() # Default to dark
        self.theme_switch.pack(side="left", padx=(0, 20))

        # Log Toggle
        self.log_visible = True
        self.btn_log = ctk.CTkButton(btn_frame, text="Hide Logs", fg_color="transparent", border_width=1, border_color=STYLES["text_sub"], hover_color=STYLES["second"], 
                      text_color=STYLES["text"], font=FONTS["body"], width=100, height=36, corner_radius=8,
                      command=self.toggle_logs)
        self.btn_log.pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(btn_frame, text="Check Updates", fg_color="transparent", border_width=1, border_color=STYLES["text_sub"], hover_color=STYLES["second"], 
                      text_color=STYLES["text"], font=FONTS["body"], width=130, height=36, corner_radius=8,
                      command=self.check_update).pack(side="left", padx=(0, 10))
                      
        ctk.CTkButton(btn_frame, text="Settings", fg_color="transparent", border_width=1, border_color=STYLES["text_sub"], hover_color=STYLES["second"],
                      text_color=STYLES["text"], font=FONTS["body"], width=100, height=36, corner_radius=8,
                      command=self.open_settings).pack(side="left")

        # --- Main Content Area ---
        self.content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        # Left: Controls (Tabs)
        self.left_frame = ctk.CTkFrame(self.content, fg_color=STYLES["card"], corner_radius=16, border_width=1, border_color=STYLES["border"])
        self.left_frame.place(relx=0.0, rely=0.0, relwidth=0.68, relheight=1.0)

        # Right: Log/Status
        self.right_frame = ctk.CTkFrame(self.content, fg_color=STYLES["card"], corner_radius=16, border_width=1, border_color=STYLES["border"])
        self.right_frame.place(relx=0.70, rely=0.0, relwidth=0.30, relheight=1.0)

        # --- Tabs ---
        self.tabview = ctk.CTkTabview(self.left_frame, width=10, fg_color="transparent", 
                                      segmented_button_fg_color=STYLES["second"],
                                      segmented_button_selected_color=STYLES["accent"],
                                      segmented_button_selected_hover_color=STYLES["hover"],
                                      segmented_button_unselected_color=STYLES["second"],
                                      segmented_button_unselected_hover_color=STYLES["border"],
                                      text_color=STYLES["text_sub"])
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.tabview.add("Single")
        self.tabview.add("Batch")
        self.tabview.add("Playlist")
        
        # Make tab backgrounds transparent
        for tab_name in ["Single", "Batch", "Playlist"]:
            self.tabview.tab(tab_name).configure(fg_color="transparent")
        
        # --- Single Tab ---
        single = self.tabview.tab("Single")
        
        ctk.CTkLabel(single, text="Video URL", text_color=STYLES["text"], font=FONTS["bold"]).pack(anchor="w", pady=(10, 6))
        self.single_url = ctk.CTkEntry(single, placeholder_text="Paste link here...", width=500, height=42, 
                                       fg_color=STYLES["second"], border_width=0, text_color=STYLES["text"], font=FONTS["body"], corner_radius=10)
        self.single_url.pack(fill="x", pady=(0, 20))

        # Options Grid
        opts = ctk.CTkFrame(single, fg_color="transparent")
        opts.pack(fill="x", pady=(0, 20))
        
        # Mode Selection
        ctk.CTkLabel(opts, text="Format", text_color=STYLES["text"], font=FONTS["bold"]).grid(row=0, column=0, sticky="w", padx=(0,20), pady=(0,6))
        self.mode_var = ctk.StringVar(value="video")
        
        radio_frame = ctk.CTkFrame(opts, fg_color="transparent")
        radio_frame.grid(row=1, column=0, sticky="w", padx=(0,20))
        
        ctk.CTkRadioButton(radio_frame, text="Video (MP4)", variable=self.mode_var, value="video", 
                           fg_color=STYLES["accent"], hover_color=STYLES["hover"], text_color=STYLES["text"], font=FONTS["body"]).pack(side="left", padx=(0,15))
        ctk.CTkRadioButton(radio_frame, text="Audio Only", variable=self.mode_var, value="audio", 
                           fg_color=STYLES["accent"], hover_color=STYLES["hover"], text_color=STYLES["text"], font=FONTS["body"]).pack(side="left")

        # Audio Format
        ctk.CTkLabel(opts, text="Audio Ext", text_color=STYLES["text"], font=FONTS["bold"]).grid(row=0, column=1, sticky="w", pady=(0,6))
        self.audio_format = ctk.CTkOptionMenu(opts, values=["m4a", "mp3"], variable=ctk.StringVar(value=cfg.get("audio_format","m4a")),
                                              fg_color=STYLES["second"], button_color=STYLES["second"], button_hover_color=STYLES["border"], 
                                              text_color=STYLES["text"], font=FONTS["body"], width=100, height=32, corner_radius=8)
        self.audio_format.grid(row=1, column=1, sticky="w")

        # Download Path
        ctk.CTkLabel(single, text="Save Location", text_color=STYLES["text"], font=FONTS["bold"]).pack(anchor="w", pady=(10, 6))
        path_row = ctk.CTkFrame(single, fg_color="transparent")
        path_row.pack(fill="x", pady=(0, 20))
        
        self.folder_var = ctk.StringVar(value=cfg.get("download_folder", DEFAULT_DOWNLOAD))
        self.folder_entry = ctk.CTkEntry(path_row, textvariable=self.folder_var, height=42, 
                                         fg_color=STYLES["second"], border_width=0, text_color=STYLES["text"], font=FONTS["body"], corner_radius=10)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(path_row, text="Browse", fg_color=STYLES["second"], hover_color=STYLES["border"], text_color=STYLES["text"], width=80, height=42, corner_radius=10,
                      command=self.browse_folder).pack(side="right")

        # Info & Progress
        self.lbl_title = ctk.CTkLabel(single, text="Ready to download", text_color=STYLES["text"], font=FONTS["bold"])
        self.lbl_title.pack(anchor="w", pady=(0, 4))
        
        self.lbl_status = ctk.CTkLabel(single, text="Waiting...", text_color=STYLES["text_sub"], font=FONTS["sub"])
        self.lbl_status.pack(anchor="w", pady=(0, 10))

        self.single_progress = ctk.CTkProgressBar(single, height=10, progress_color=STYLES["accent"], fg_color=STYLES["second"])
        self.single_progress.set(0.0)
        self.single_progress.pack(fill="x", pady=(0, 5))
        
        self.single_pct_label = ctk.CTkLabel(single, text="0%", text_color=STYLES["text_sub"], font=FONTS["sub"])
        self.single_pct_label.pack(anchor="e")

        # Action Buttons
        btn_row = ctk.CTkFrame(single, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))
        
        self.single_btn = ctk.CTkButton(btn_row, text="Download Now", fg_color=STYLES["accent"], hover_color=STYLES["hover"], 
                                        text_color="#ffffff", font=("Google Sans Code", 15, "bold"), height=48, corner_radius=12,
                                        command=self.start_single_download)
        self.single_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_cancel_single = ctk.CTkButton(btn_row, text="Cancel", fg_color="#ef4444", hover_color="#dc2626", 
                                               text_color="#ffffff", font=("Google Sans Code", 15, "bold"), height=48, corner_radius=12,
                                               command=self.cancel_single, state="disabled")
        self.btn_cancel_single.pack(side="right")

        # --- Batch Tab ---
        batch = self.tabview.tab("Batch")
        ctk.CTkLabel(batch, text="URLs (One per line)", text_color=STYLES["text"], font=FONTS["bold"]).pack(anchor="w", pady=(10, 6))
        self.batch_text = ctk.CTkTextbox(batch, height=160, fg_color=STYLES["second"], text_color=STYLES["text"], font=FONTS["body"], corner_radius=10, border_width=0)
        self.batch_text.pack(fill="both", expand=True, pady=(0, 10))
        
        # Batch Info
        self.lbl_batch_title = ctk.CTkLabel(batch, text="Ready", text_color=STYLES["text"], font=FONTS["bold"])
        self.lbl_batch_title.pack(anchor="w")
        
        self.batch_progress = ctk.CTkProgressBar(batch, height=10, progress_color=STYLES["accent"], fg_color=STYLES["second"])
        self.batch_progress.set(0.0)
        self.batch_progress.pack(fill="x", pady=(5, 5))
        
        self.batch_pct_label = ctk.CTkLabel(batch, text="0%", text_color=STYLES["text_sub"], font=FONTS["sub"])
        self.batch_pct_label.pack(anchor="e")
        
        b_btn_row = ctk.CTkFrame(batch, fg_color="transparent")
        b_btn_row.pack(fill="x", pady=(10, 0))
        
        self.batch_btn = ctk.CTkButton(b_btn_row, text="Download All", fg_color=STYLES["accent"], hover_color=STYLES["hover"], 
                                       text_color="#ffffff", font=("Google Sans Code", 15, "bold"), height=48, corner_radius=12,
                                       command=self.start_batch_download)
        self.batch_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_cancel_batch = ctk.CTkButton(b_btn_row, text="Cancel", fg_color="#ef4444", hover_color="#dc2626",
                                              text_color="#ffffff", font=("Google Sans Code", 15, "bold"), height=48, corner_radius=12,
                                              command=self.cancel_batch, state="disabled")
        self.btn_cancel_batch.pack(side="right")

        # --- Playlist Tab ---
        playlist = self.tabview.tab("Playlist")
        ctk.CTkLabel(playlist, text="Playlist URL", text_color=STYLES["text"], font=FONTS["bold"]).pack(anchor="w", pady=(10, 6))
        self.playlist_url = ctk.CTkEntry(playlist, placeholder_text="Paste playlist link...", height=42, 
                                         fg_color=STYLES["second"], border_width=0, text_color=STYLES["text"], font=FONTS["body"], corner_radius=10)
        self.playlist_url.pack(fill="x", pady=(0, 20))
        
        self.lbl_pl_title = ctk.CTkLabel(playlist, text="Ready", text_color=STYLES["text"], font=FONTS["bold"])
        self.lbl_pl_title.pack(anchor="w")
        
        self.playlist_progress = ctk.CTkProgressBar(playlist, height=10, progress_color=STYLES["accent"], fg_color=STYLES["second"])
        self.playlist_progress.set(0.0)
        self.playlist_progress.pack(fill="x", pady=(5, 5))
        
        self.playlist_pct_label = ctk.CTkLabel(playlist, text="0%", text_color=STYLES["text_sub"], font=FONTS["sub"])
        self.playlist_pct_label.pack(anchor="e")
        
        p_btn_row = ctk.CTkFrame(playlist, fg_color="transparent")
        p_btn_row.pack(fill="x", pady=(10, 0))
        
        self.playlist_btn = ctk.CTkButton(p_btn_row, text="Download Playlist", fg_color=STYLES["accent"], hover_color=STYLES["hover"], 
                                          text_color="#ffffff", font=("Google Sans Code", 15, "bold"), height=48, corner_radius=12,
                                          command=self.start_playlist_download)
        self.playlist_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_cancel_pl = ctk.CTkButton(p_btn_row, text="Cancel", fg_color="#ef4444", hover_color="#dc2626",
                                           text_color="#ffffff", font=("Google Sans Code", 15, "bold"), height=48, corner_radius=12,
                                           command=self.cancel_playlist, state="disabled")
        self.btn_cancel_pl.pack(side="right")

        # --- Right Pane (Log) ---
        ctk.CTkLabel(self.right_frame, text="Activity Log", text_color=STYLES["text"], font=FONTS["bold"]).pack(anchor="w", padx=16, pady=(16, 10))
        
        self.logbox = ctk.CTkTextbox(self.right_frame, fg_color=STYLES["bg"], text_color=STYLES["text_sub"], font=FONTS["mono"], corner_radius=8)
        self.logbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.logbox.insert("0.0", "System Ready.\n")
        self.logbox.configure(state="disabled")

        # Managers
        self.single_mgr = DownloadManager()
        self.batch_mgr = DownloadManager()
        self.playlist_mgr = DownloadManager()

        # regularly process UI queue
        self.after(100, self._process_ui_queue)

    # ---------------------------
    # UI helpers
    # ---------------------------
    def toggle_theme(self):
        mode = self.theme_switch.get()
        if mode == "light":
            ctk.set_appearance_mode("Light")
            # Force update gradient for light mode if needed, 
            # but CTkImage handles light/dark automatically if we set it up right!
            # We set light_image=base_l, dark_image=base_d in create_gradient.
            # So CTk should handle the image switch automatically when appearance mode changes.
            # However, let's verify if we need to re-configure to trigger it.
            # Usually ctk.set_appearance_mode triggers the update.
        else:
            ctk.set_appearance_mode("Dark")
            
    def toggle_logs(self):
        if self.log_visible:
            self.right_frame.place_forget()
            self.left_frame.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0)
            self.btn_log.configure(text="Show Logs")
            self.log_visible = False
        else:
            self.right_frame.place(relx=0.70, rely=0.0, relwidth=0.30, relheight=1.0)
            self.left_frame.place(relx=0.0, rely=0.0, relwidth=0.68, relheight=1.0)
            self.btn_log.configure(text="Hide Logs")
            self.log_visible = True

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
            cfg["download_folder"] = folder
            save_config(cfg)

    def _append_log(self, text):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", f"{text}\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _process_ui_queue(self):
        try:
            while True:
                fn, a, kw = ui_queue.get_nowait()
                try:
                    fn(*a, **kw)
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.after(100, self._process_ui_queue)

    # ---------------------------
    # Cancel Methods
    # ---------------------------
    def cancel_single(self):
        self.single_mgr.cancel()
        self.btn_cancel_single.configure(state="disabled")
        enqueue_ui(self._append_log, "Single download cancelled by user.")

    def cancel_batch(self):
        self.batch_mgr.cancel()
        self.btn_cancel_batch.configure(state="disabled")
        enqueue_ui(self._append_log, "Batch download cancelled by user.")

    def cancel_playlist(self):
        self.playlist_mgr.cancel()
        self.btn_cancel_pl.configure(state="disabled")
        enqueue_ui(self._append_log, "Playlist download cancelled by user.")

    # ---------------------------
    # Downloads (single, batch, playlist)
    # ---------------------------
    def start_single_download(self):
        threading.Thread(target=self._single_download_worker, daemon=True).start()

    def _single_download_worker(self):
        url = self.single_url.get().strip()
        if not url:
            messagebox.showerror("Error", "Please paste a URL.")
            return
        folder = self.folder_var.get().strip() or cfg.get("download_folder", DEFAULT_DOWNLOAD)
        os.makedirs(folder, exist_ok=True)
        cfg["download_folder"] = folder
        save_config(cfg)

        mode = self.mode_var.get()
        audio_fmt = self.audio_format.get()

        if not os.path.isfile(YTDLP) or not os.path.isfile(FFMPEG):
            messagebox.showerror("Error", "Tools missing (yt-dlp/ffmpeg).")
            return

        output = os.path.join(folder, "%(title)s.%(ext)s")
        if mode == "audio":
            cmd = [YTDLP, "-x", "--audio-format", audio_fmt, "--ffmpeg-location", FFMPEG, "-o", output, url]
        else:
            cmd = [YTDLP, "-f", "bestvideo+bestaudio", "--ffmpeg-location", FFMPEG, "--merge-output-format", "mp4", "-o", output, url]

        # reset UI
        enqueue_ui(self.single_progress.set, 0.0)
        enqueue_ui(self.single_pct_label.configure, text="0%")
        
        enqueue_ui(self.lbl_title.configure, text="Fetching info...")
        enqueue_ui(self.lbl_status.configure, text="Starting...")
        enqueue_ui(self.single_btn.configure, state="disabled")
        enqueue_ui(self.btn_cancel_single.configure, state="normal")
        enqueue_ui(self._append_log, f"Starting single download: {url}")

        current_type = "video" if mode == "video" else "audio"

        def line_cb(line):
            nonlocal current_type
            # 1. Parse Progress
            m = PERC_RE.search(line)
            if m:
                try:
                    pct = float(m.group(1)) / 100.0
                    enqueue_ui(self.single_progress.set, pct)
                    enqueue_ui(self.single_pct_label.configure, text=f"{m.group(1)}%")
                except:
                    pass
            
            # 2. Parse Title (Destination: ...)
            if "[download] Destination:" in line:
                # Extract filename as title proxy
                try:
                    fname = line.split("Destination:", 1)[1].strip()
                    # Determine type based on extension
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in ['.m4a', '.mp3', '.opus', '.aac', '.wav']:
                        current_type = "audio"
                        enqueue_ui(self.lbl_status.configure, text="Downloading Audio...")
                        # Reset progress for audio phase if we were doing video before
                        # But yt-dlp usually outputs 0% at start of new file, so it might handle itself.
                        # However, to be safe, we can force a reset if we detect a switch, but 
                        # yt-dlp output is sequential.
                    elif ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov']:
                        current_type = "video"
                        enqueue_ui(self.lbl_status.configure, text="Downloading Video...")

                    # remove path and ext for cleaner look
                    fname = os.path.basename(fname)
                    fname = os.path.splitext(fname)[0]
                    enqueue_ui(self.lbl_title.configure, text=fname)
                except:
                    pass
            elif "[download]" in line and "has already been downloaded" in line:
                enqueue_ui(self.lbl_title.configure, text="Already downloaded")
                enqueue_ui(self.single_progress.set, 1.0)
                enqueue_ui(self.single_pct_label.configure, text="100%")

            # 3. Parse Status
            if "[Merger]" in line:
                enqueue_ui(self.lbl_status.configure, text="Merging Video & Audio...")
                # Optional: set progress to indeterminate or 100%
                enqueue_ui(self.single_progress.set, 1.0)
                enqueue_ui(self.single_pct_label.configure, text="100%")
            elif "[ExtractAudio]" in line:
                enqueue_ui(self.lbl_status.configure, text="Extracting Audio...")
            elif "[download]" in line and "100%" in line:
                # This happens at end of each file
                pass
            elif "Destination" in line:
                # Fallback
                pass

            enqueue_ui(self._append_log, line.strip())

        rc, msg = self.single_mgr.start(cmd, line_callback=line_cb)
        
        enqueue_ui(self.single_btn.configure, state="normal")
        enqueue_ui(self.btn_cancel_single.configure, state="disabled")

        if rc == 0:
            enqueue_ui(self.single_progress.set, 1.0)
            enqueue_ui(self.single_pct_label.configure, text="100%")
            enqueue_ui(self.lbl_status.configure, text="Finished.")
            enqueue_ui(self._append_log, "Single download finished.")
            if cfg.get("auto_open_folder", True):
                try: os.startfile(folder)
                except: pass
        elif rc == -1:
             enqueue_ui(self.lbl_status.configure, text="Cancelled.")
        else:
            enqueue_ui(self.lbl_status.configure, text="Error.")
            enqueue_ui(self._append_log, f"Single download failed (code {rc}).")

    # ---------------------------
    def start_batch_download(self):
        threading.Thread(target=self._batch_worker, daemon=True).start()

    def _batch_worker(self):
        text = self.batch_text.get("0.0", "end").strip()
        if not text:
            messagebox.showerror("Error", "Paste at least one URL (one per line).")
            return
        urls = [u.strip() for u in text.splitlines() if u.strip()]
        total = len(urls)
        folder = self.folder_var.get().strip() or cfg.get("download_folder", DEFAULT_DOWNLOAD)
        os.makedirs(folder, exist_ok=True)
        cfg["download_folder"] = folder
        save_config(cfg)

        if not os.path.isfile(YTDLP) or not os.path.isfile(FFMPEG):
            messagebox.showerror("Error", "yt-dlp.exe or ffmpeg.exe missing.")
            return

        enqueue_ui(self._append_log, f"Starting batch download ({total} items)...")
        enqueue_ui(self.batch_btn.configure, state="disabled")
        enqueue_ui(self.btn_cancel_batch.configure, state="normal")
        completed = 0
        enqueue_ui(self.batch_pct_label.configure, text="0%")

        for idx, url in enumerate(urls, start=1):
            if self.batch_mgr.cancelled:
                break

            enqueue_ui(self._append_log, f"[{idx}/{total}] Starting: {url}")
            enqueue_ui(self.lbl_batch_title.configure, text=f"Item {idx}/{total}: Fetching...")
            
            output = os.path.join(folder, "%(title)s.%(ext)s")
            cmd = [YTDLP, "-f", "bestvideo+bestaudio", "--ffmpeg-location", FFMPEG, "--merge-output-format", "mp4", "-o", output, url]

            def line_cb(line):
                # Parse Title
                if "[download] Destination:" in line:
                    try:
                        fname = line.split("Destination:", 1)[1].strip()
                        fname = os.path.basename(fname)
                        fname = os.path.splitext(fname)[0]
                        enqueue_ui(self.lbl_batch_title.configure, text=f"Item {idx}/{total}: {fname}")
                    except:
                        pass
                
                m = PERC_RE.search(line)
                if m:
                    try:
                        pct = float(m.group(1))/100.0
                        # Show current item progress directly
                        enqueue_ui(self.batch_progress.set, pct)
                        enqueue_ui(self.batch_pct_label.configure, text=f"{m.group(1)}%")
                    except:
                        pass
                else:
                    enqueue_ui(self._append_log, f"[{idx}/{total}] {line.strip()}")

            rc, msg = self.batch_mgr.start(cmd, line_callback=line_cb)
            
            if rc == 0:
                completed += 1
                enqueue_ui(self._append_log, f"[{idx}/{total}] Completed.")
            elif rc == -1:
                enqueue_ui(self._append_log, f"[{idx}/{total}] Cancelled.")
                break
            else:
                enqueue_ui(self._append_log, f"[{idx}/{total}] Failed (code {rc}).")
            
            # Reset for next item
            enqueue_ui(self.batch_progress.set, 0.0)
            enqueue_ui(self.batch_pct_label.configure, text="0%")

        enqueue_ui(self.batch_btn.configure, state="normal")
        enqueue_ui(self.btn_cancel_batch.configure, state="disabled")
        enqueue_ui(self.lbl_batch_title.configure, text="Batch Finished")
        enqueue_ui(self._append_log, f"Batch finished: {completed}/{total} succeeded.")
        
        if cfg.get("auto_open_folder", True):
            try: os.startfile(folder)
            except: pass

    # ---------------------------
    def start_playlist_download(self):
        threading.Thread(target=self._playlist_worker, daemon=True).start()

    def _playlist_worker(self):
        url = self.playlist_url.get().strip()
        if not url:
            messagebox.showerror("Error", "Please paste a playlist URL.")
            return
        folder = self.folder_var.get().strip() or cfg.get("download_folder", DEFAULT_DOWNLOAD)
        os.makedirs(folder, exist_ok=True)
        cfg["download_folder"] = folder
        save_config(cfg)

        if not os.path.isfile(YTDLP) or not os.path.isfile(FFMPEG):
            messagebox.showerror("Error", "yt-dlp.exe or ffmpeg.exe missing.")
            return

        enqueue_ui(self.playlist_btn.configure, state="disabled")
        enqueue_ui(self.btn_cancel_pl.configure, state="normal")
        enqueue_ui(self.lbl_pl_title.configure, text="Fetching playlist info...")

        # Use yt-dlp to fetch playlist metadata: get playlist count, then download
        enqueue_ui(self._append_log, "Fetching playlist info...")
        # get list of video URLs in playlist
        cmd_info = [YTDLP, "--flat-playlist", "-J", url]  # JSON output
        
        # We use run_process_stream here because it's a quick info fetch
        rc, out = run_process_stream(cmd_info)
        if rc != 0:
            enqueue_ui(self._append_log, "Failed to fetch playlist info.")
            enqueue_ui(self.playlist_btn.configure, state="normal")
            enqueue_ui(self.btn_cancel_pl.configure, state="disabled")
            return

        # parse JSON safely
        try:
            import json as _json
            j = _json.loads(out)
            entries = j.get("entries", [])
            total = len(entries)
        except Exception:
            # fallback: let yt-dlp handle playlist download directly
            total = None

        enqueue_ui(self._append_log, f"Starting playlist download (approx. {total if total else 'unknown'} items)...")
        enqueue_ui(self.playlist_pct_label.configure, text="0%")

        # let yt-dlp handle the playlist downloading (simpler)
        cmd_dl = [YTDLP, "-f", "bestvideo+bestaudio", "--ffmpeg-location", FFMPEG,
                  "--yes-playlist", "--merge-output-format", "mp4", "-o", os.path.join(folder, "%(playlist_index)s - %(title)s.%(ext)s"), url]

        total_items = total if total else 1
        current_item = 1

        def line_cb(line):
            # Parse "Downloading video X of Y"
            if "Downloading video" in line and "of" in line:
                try:
                    parts = line.split("Downloading video")[1].strip().split("of")
                    curr = int(parts[0].strip())
                    tot = int(parts[1].strip())
                    nonlocal total_items, current_item
                    current_item = curr
                    total_items = tot
                except:
                    pass
            
            # Parse Title
            if "[download] Destination:" in line:
                try:
                    fname = line.split("Destination:", 1)[1].strip()
                    fname = os.path.basename(fname)
                    fname = os.path.splitext(fname)[0]
                    enqueue_ui(self.lbl_pl_title.configure, text=f"[{current_item}/{total_items}] {fname}")
                except:
                    pass

            m = PERC_RE.search(line)
            if m:
                pct = float(m.group(1))/100.0
                # Show current item progress directly
                enqueue_ui(self.playlist_progress.set, pct)
                enqueue_ui(self.playlist_pct_label.configure, text=f"{m.group(1)}%") 
            else:
                enqueue_ui(self._append_log, f"[playlist] {line.strip()}")

        rc, msg = self.playlist_mgr.start(cmd_dl, line_callback=line_cb)
        
        enqueue_ui(self.playlist_btn.configure, state="normal")
        enqueue_ui(self.btn_cancel_pl.configure, state="disabled")
        
        if rc == 0:
            enqueue_ui(self._append_log, "Playlist download completed.")
            enqueue_ui(self.playlist_pct_label.configure, text="100%")
            enqueue_ui(self.lbl_pl_title.configure, text="Playlist Finished")
            if cfg.get("auto_open_folder", True):
                try: os.startfile(folder)
                except: pass
        elif rc == -1:
            enqueue_ui(self.lbl_pl_title.configure, text="Cancelled")
            enqueue_ui(self._append_log, "Playlist download cancelled.")
        else:
            enqueue_ui(self.lbl_pl_title.configure, text="Error")
            enqueue_ui(self._append_log, "Playlist download failed.")

    # ---------------------------
    # Update / settings
    # ---------------------------
    def check_update(self):
        def worker():
            def cb(msg): enqueue_ui(self._append_log, msg)
            ok,msg = update_ytdlp(cb)
            enqueue_ui(self._append_log, f"Update: {msg}")
            if ok:
                messagebox.showinfo("yt-dlp Update", msg)
        threading.Thread(target=worker, daemon=True).start()

    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.geometry("500x400")
        win.configure(fg_color=BG)
        try:
            win.iconbitmap(cfg.get("app_icon", ICON_PATH))
        except: pass

        ctk.CTkLabel(win, text="Preferences", text_color=TEXT, font=FONT_HEADER).pack(anchor="w", padx=24, pady=(20, 10))

        # Container
        container = ctk.CTkFrame(win, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER)
        container.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        # Default Folder
        ctk.CTkLabel(container, text="Default Download Folder", text_color=TEXT_SUB, font=FONT_BOLD).pack(anchor="w", padx=20, pady=(20, 6))
        
        frame_folder = ctk.CTkFrame(container, fg_color="transparent")
        frame_folder.pack(fill="x", padx=20, pady=(0, 10))
        
        df_var = ctk.StringVar(value=cfg.get("download_folder", DEFAULT_DOWNLOAD))
        e = ctk.CTkEntry(frame_folder, textvariable=df_var, height=42, fg_color=SECOND, border_width=0, text_color=TEXT, font=FONT_BODY, corner_radius=10)
        e.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(frame_folder, text="Browse", fg_color=SECOND, hover_color=BORDER, text_color=TEXT, width=80, height=42, corner_radius=10,
                      command=lambda: df_var.set(filedialog.askdirectory())).pack(side="right")

        # Theme (Simplified since we enforce dark now, but keeping for structure)
        # We can remove theme selection if we want to enforce the new look, or keep it. 
        # The user asked for "sleek and modern", usually implies a specific curated look.
        # I will hide the theme selector to enforce the new premium design, but keep the toggles.
        
        # Toggles
        ctk.CTkLabel(container, text="Behavior", text_color=TEXT_SUB, font=FONT_BOLD).pack(anchor="w", padx=20, pady=(10, 6))
        
        auto_open_var = ctk.BooleanVar(value=cfg.get("auto_open_folder", True))
        auto_update_var = ctk.BooleanVar(value=cfg.get("auto_update_ytdlp", True))
        
        ctk.CTkCheckBox(container, text="Auto-open folder after download", variable=auto_open_var, 
                        fg_color=ACCENT, hover_color=HOVER, text_color=TEXT, font=FONT_BODY, border_color=BORDER).pack(anchor="w", padx=20, pady=8)
                        
        ctk.CTkCheckBox(container, text="Auto-update yt-dlp on start", variable=auto_update_var,
                        fg_color=ACCENT, hover_color=HOVER, text_color=TEXT, font=FONT_BODY, border_color=BORDER).pack(anchor="w", padx=20, pady=8)

        def save_and_close():
            cfg["download_folder"] = df_var.get() or cfg.get("download_folder")
            # cfg["theme"] = theme_var.get() # Removed theme choice
            cfg["auto_open_folder"] = bool(auto_open_var.get())
            cfg["auto_update_ytdlp"] = bool(auto_update_var.get())
            save_config(cfg)
            win.destroy()

        ctk.CTkButton(win, text="Save Changes", fg_color=ACCENT, hover_color=HOVER, text_color="#ffffff", 
                      font=("Roboto Medium", 15), height=48, corner_radius=12,
                      command=save_and_close).pack(fill="x", padx=24, pady=(0, 24))

# ---------------------------
# Run app
# ---------------------------
def main():
    app = DownloaderApp()
    # apply initial theme mode (enforce dark for new design)
    ctk.set_appearance_mode("Dark")
    app.mainloop()

if __name__ == "__main__":
    main()
