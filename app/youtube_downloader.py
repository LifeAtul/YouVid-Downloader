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

YTDLP = os.path.join(REAL_BASE, "ytdlp", "yt-dlp.exe")
FFMPEG = os.path.join(REAL_BASE, "ffmpeg", "ffmpeg.exe")

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
# yt-dlp progress parsing
# ---------------------------
PERC_RE = re.compile(r"(\d{1,3}\.\d+)%")

def run_process_stream(cmd, line_callback=None):
    """Run subprocess and stream stdout lines. Hide a console on Windows for subprocesses."""
    creationflags = 0
    if os.name == "nt":
        # CREATE_NO_WINDOW = 0x08000000
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
# UI: CustomTkinter styling
# ---------------------------
# Configure appearance: we use dark theme, but deep-black background and modern controls
ctk.set_appearance_mode("Dark")  # or "Light"
ctk.set_default_color_theme("dark-blue")  # built-in theme, looks modern

# tweak styles by overriding colors
BG = "#0b0b0b"        # near-black background
CARD = "#111216"
ACCENT = "#1DB954"    # green accent like Spotify
SECOND = "#2b2b2b"
TEXT = "#e6e6e6"

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
        self.title("YouTube Downloader — Modern")
        self.geometry("900x560")
        self.minsize(820,520)
        # set icon if available
        try:
            self.iconbitmap(cfg.get("app_icon", ICON_PATH))
        except Exception:
            pass

        # top frame: title + settings
        header = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        header.pack(fill="x", padx=12, pady=(12,6))
        title = ctk.CTkLabel(header, text="YouTube Downloader", font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT)
        title.pack(side="left", padx=6)
        subtitle = ctk.CTkLabel(header, text="Modern black theme • Fast downloads • Playlist & Batch", text_color="#98a0a6")
        subtitle.pack(side="left", padx=(12,0))

        btn_settings = ctk.CTkButton(header, text="Settings", fg_color=SECOND, hover_color="#333", command=self.open_settings, width=110)
        btn_settings.pack(side="right", padx=8)
        btn_update = ctk.CTkButton(header, text="Check yt-dlp", fg_color=SECOND, hover_color="#333", command=self.check_update, width=140)
        btn_update.pack(side="right", padx=8)

        # main content
        content = ctk.CTkFrame(self, fg_color=BG, corner_radius=8)
        content.pack(fill="both", expand=True, padx=12, pady=(0,12))

        # left: controls and tabs
        left = ctk.CTkFrame(content, fg_color=CARD, corner_radius=8)
        left.place(relx=0.02, rely=0.04, relwidth=0.66, relheight=0.9)

        # right: log and queue
        right = ctk.CTkFrame(content, fg_color=CARD, corner_radius=8)
        right.place(relx=0.70, rely=0.04, relwidth=0.28, relheight=0.9)

        # Tabs
        tabview = ctk.CTkTabview(left, width=10)
        tabview.pack(fill="both", expand=True, padx=12, pady=12)
        tabview.add("Single")
        tabview.add("Batch")
        tabview.add("Playlist")

        # --- Single Tab ---
        single = tabview.tab("Single")
        ctk.CTkLabel(single, text="Single Video", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=6, pady=(6,0))

        ctk.CTkLabel(single, text="Paste a YouTube video URL:", text_color="#bfc6c9").pack(anchor="w", padx=6, pady=(8,0))
        self.single_url = ctk.CTkEntry(single, placeholder_text="https://www.youtube.com/watch?v=...", width=640)
        self.single_url.pack(padx=6, pady=(6,8))

        # mode and audio format
        mode_frame = ctk.CTkFrame(single, fg_color=SECOND)
        mode_frame.pack(fill="x", padx=6, pady=(4,6))
        self.mode_var = ctk.StringVar(value="video")
        ctk.CTkRadioButton(mode_frame, text="Video", variable=self.mode_var, value="video").pack(side="left", padx=8, pady=8)
        ctk.CTkRadioButton(mode_frame, text="Audio Only", variable=self.mode_var, value="audio").pack(side="left", padx=8)
        ctk.CTkLabel(mode_frame, text="Audio format:", text_color="#bfc6c9").pack(side="left", padx=(12,4))
        self.audio_format = ctk.CTkOptionMenu(mode_frame, values=["m4a", "mp3"], variable=ctk.StringVar(value=cfg.get("audio_format","m4a")))
        self.audio_format.set(cfg.get("audio_format","m4a"))
        self.audio_format.pack(side="left", padx=6)

        # download folder row
        folder_row = ctk.CTkFrame(single, fg_color=SECOND)
        folder_row.pack(fill="x", padx=6, pady=(8,6))
        ctk.CTkLabel(folder_row, text="Download folder:", text_color="#bfc6c9").pack(side="left", padx=(6,8))
        self.folder_var = ctk.StringVar(value=cfg.get("download_folder", DEFAULT_DOWNLOAD))
        self.folder_entry = ctk.CTkEntry(folder_row, textvariable=self.folder_var, width=420)
        self.folder_entry.pack(side="left", padx=(0,8), pady=6)
        ctk.CTkButton(folder_row, text="Browse", command=self.browse_folder, width=80).pack(side="left")

        # download button + progress
        dl_row = ctk.CTkFrame(single, fg_color=SECOND)
        dl_row.pack(fill="x", padx=6, pady=(8,6))
        self.single_btn = ctk.CTkButton(dl_row, text="Download", fg_color=ACCENT, hover_color="#1ed85b", command=self.start_single_download, width=160)
        self.single_btn.pack(side="left", padx=10, pady=8)
        self.single_progress = ctk.CTkProgressBar(dl_row, width=420)
        self.single_progress.set(0.0)
        self.single_progress.pack(side="left", padx=10)

        # --- Batch Tab ---
        batch = tabview.tab("Batch")
        ctk.CTkLabel(batch, text="Batch Download", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=6, pady=(6,0))
        ctk.CTkLabel(batch, text="Paste multiple URLs (one per line):", text_color="#bfc6c9").pack(anchor="w", padx=6, pady=(8,0))
        self.batch_text = ctk.CTkTextbox(batch, width=760, height=220)
        self.batch_text.pack(padx=6, pady=8)
        batch_controls = ctk.CTkFrame(batch, fg_color=SECOND)
        batch_controls.pack(fill="x", padx=6, pady=(6,8))
        self.batch_btn = ctk.CTkButton(batch_controls, text="Start Batch Download", fg_color=ACCENT, command=self.start_batch_download, width=200)
        self.batch_btn.pack(side="left", padx=8)
        self.batch_progress = ctk.CTkProgressBar(batch_controls, width=420)
        self.batch_progress.set(0.0)
        self.batch_progress.pack(side="left", padx=8)

        # --- Playlist Tab ---
        playlist = tabview.tab("Playlist")
        ctk.CTkLabel(playlist, text="Download Playlist", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=6, pady=(6,0))
        ctk.CTkLabel(playlist, text="Paste a playlist URL:", text_color="#bfc6c9").pack(anchor="w", padx=6, pady=(8,0))
        self.playlist_url = ctk.CTkEntry(playlist, placeholder_text="https://www.youtube.com/playlist?list=...", width=760)
        self.playlist_url.pack(padx=6, pady=(6,8))
        pl_controls = ctk.CTkFrame(playlist, fg_color=SECOND)
        pl_controls.pack(fill="x", padx=6, pady=(6,8))
        self.playlist_btn = ctk.CTkButton(pl_controls, text="Download Playlist", fg_color=ACCENT, command=self.start_playlist_download, width=200)
        self.playlist_btn.pack(side="left", padx=8)
        self.playlist_progress = ctk.CTkProgressBar(pl_controls, width=420)
        self.playlist_progress.set(0.0)
        self.playlist_progress.pack(side="left", padx=8)

        # --- Right pane: log & status ---
        ctk.CTkLabel(right, text="Status & Log", text_color=TEXT, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=8, pady=(8,4))
        self.logbox = ctk.CTkTextbox(right, width=320, height=420, state="normal")
        self.logbox.pack(padx=8, pady=6)
        self.logbox.insert("0.0", "Ready.\n")
        self.logbox.configure(state="disabled")

        # regularly process UI queue
        self.after(100, self._process_ui_queue)

    # ---------------------------
    # UI helpers
    # ---------------------------
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

        if not os.path.isfile(YTDLP):
            messagebox.showerror("Error", "yt-dlp.exe not found in /ytdlp/")
            return
        if not os.path.isfile(FFMPEG):
            messagebox.showerror("Error", "ffmpeg.exe not found in /ffmpeg/")
            return

        output = os.path.join(folder, "%(title)s.%(ext)s")
        if mode == "audio":
            cmd = [YTDLP, "-x", "--audio-format", audio_fmt, "--ffmpeg-location", FFMPEG, "-o", output, url]
        else:
            cmd = [YTDLP, "-f", "bestvideo+bestaudio", "--ffmpeg-location", FFMPEG, "--merge-output-format", "mp4", "-o", output, url]

        # reset UI
        enqueue_ui(self.single_progress.set, 0.0)
        enqueue_ui(self._append_log, f"Starting single download: {url}")

        def line_cb(line):
            m = PERC_RE.search(line)
            if m:
                try:
                    pct = float(m.group(1)) / 100.0
                    enqueue_ui(self.single_progress.set, pct)
                    enqueue_ui(self._append_log, f"{m.group(1)}%")
                except:
                    pass
            else:
                enqueue_ui(self._append_log, line.strip())

        rc, _ = run_process_stream(cmd, line_callback=line_cb)
        if rc == 0:
            enqueue_ui(self.single_progress.set, 1.0)
            enqueue_ui(self._append_log, "Single download finished.")
            if cfg.get("auto_open_folder", True):
                try: os.startfile(folder)
                except: pass
        else:
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
        completed = 0

        for idx, url in enumerate(urls, start=1):
            enqueue_ui(self._append_log, f"[{idx}/{total}] Starting: {url}")
            output = os.path.join(folder, "%(title)s.%(ext)s")
            cmd = [YTDLP, "-f", "bestvideo+bestaudio", "--ffmpeg-location", FFMPEG, "--merge-output-format", "mp4", "-o", output, url]

            def line_cb(line):
                m = PERC_RE.search(line)
                if m:
                    try:
                        pct = float(m.group(1))/100.0
                        # set per-item progress scaled into batch overall
                        overall = (idx - 1 + pct) / total
                        enqueue_ui(self.batch_progress.set, overall)
                        enqueue_ui(self._append_log, f"[{idx}/{total}] {m.group(1)}%")
                    except:
                        pass
                else:
                    enqueue_ui(self._append_log, f"[{idx}/{total}] {line.strip()}")

            rc, _ = run_process_stream(cmd, line_callback=line_cb)
            if rc == 0:
                completed += 1
                enqueue_ui(self._append_log, f"[{idx}/{total}] Completed.")
            else:
                enqueue_ui(self._append_log, f"[{idx}/{total}] Failed (code {rc}).")
            enqueue_ui(self.batch_progress.set, completed / total)

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

        # Use yt-dlp to fetch playlist metadata: get playlist count, then download
        enqueue_ui(self._append_log, "Fetching playlist info...")
        # get list of video URLs in playlist
        cmd_info = [YTDLP, "--flat-playlist", "-J", url]  # JSON output
        rc, out = run_process_stream(cmd_info)
        if rc != 0:
            enqueue_ui(self._append_log, "Failed to fetch playlist info.")
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

        # let yt-dlp handle the playlist downloading (simpler)
        cmd_dl = [YTDLP, "-f", "bestvideo+bestaudio", "--ffmpeg-location", FFMPEG,
                  "--yes-playlist", "--merge-output-format", "mp4", "-o", os.path.join(folder, "%(playlist_index)s - %(title)s.%(ext)s"), url]

        def line_cb(line):
            m = PERC_RE.search(line)
            if m and total:
                # attempt to extract index from line (this is heuristic)
                pct = float(m.group(1))/100.0
                # we cannot reliably map to overall without precise index — show current percent
                enqueue_ui(self.playlist_progress.set, pct)
                enqueue_ui(self._append_log, f"[playlist] {m.group(1)}%")
            else:
                enqueue_ui(self._append_log, f"[playlist] {line.strip()}")

        rc, _ = run_process_stream(cmd_dl, line_callback=line_cb)
        if rc == 0:
            enqueue_ui(self._append_log, "Playlist download completed.")
            if cfg.get("auto_open_folder", True):
                try: os.startfile(folder)
                except: pass
        else:
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
        win.geometry("480x340")
        win.configure(fg_color=BG)
        try:
            win.iconbitmap(cfg.get("app_icon", ICON_PATH))
        except: pass

        ctk.CTkLabel(win, text="Defaults", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=12, pady=(10,6))
        # default folder
        frame = ctk.CTkFrame(win, fg_color=SECOND)
        frame.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(frame, text="Download folder:", text_color="#bfc6c9").pack(side="left", padx=8)
        df_var = ctk.StringVar(value=cfg.get("download_folder", DEFAULT_DOWNLOAD))
        e = ctk.CTkEntry(frame, textvariable=df_var, width=360)
        e.pack(side="left", padx=8)
        ctk.CTkButton(frame, text="Browse", command=lambda: df_var.set(filedialog.askdirectory())).pack(side="left", padx=6)

        # theme
        tframe = ctk.CTkFrame(win, fg_color=SECOND)
        tframe.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(tframe, text="Theme:", text_color="#bfc6c9").pack(side="left", padx=8)
        theme_var = ctk.StringVar(value=cfg.get("theme","dark"))
        ctk.CTkOptionMenu(tframe, values=["dark","light"], variable=theme_var).pack(side="left", padx=8)

        # toggles
        t2 = ctk.CTkFrame(win, fg_color=SECOND)
        t2.pack(fill="x", padx=12, pady=8)
        auto_open_var = ctk.BooleanVar(value=cfg.get("auto_open_folder", True))
        auto_update_var = ctk.BooleanVar(value=cfg.get("auto_update_ytdlp", True))
        ctk.CTkCheckBox(t2, text="Auto-open folder after download", variable=auto_open_var).pack(anchor="w", padx=8, pady=4)
        ctk.CTkCheckBox(t2, text="Auto-update yt-dlp on start", variable=auto_update_var).pack(anchor="w", padx=8, pady=4)

        def save_and_close():
            cfg["download_folder"] = df_var.get() or cfg.get("download_folder")
            cfg["theme"] = theme_var.get()
            cfg["auto_open_folder"] = bool(auto_open_var.get())
            cfg["auto_update_ytdlp"] = bool(auto_update_var.get())
            save_config(cfg)
            # apply theme setting
            if cfg["theme"] == "light":
                ctk.set_appearance_mode("Light")
            else:
                ctk.set_appearance_mode("Dark")
            win.destroy()

        ctk.CTkButton(win, text="Save", fg_color=ACCENT, command=save_and_close).pack(pady=12)

# ---------------------------
# Run app
# ---------------------------
def main():
    app = DownloaderApp()
    # apply initial theme mode (we force dark appearance with black background)
    if cfg.get("theme","dark") == "light":
        ctk.set_appearance_mode("Light")
    else:
        ctk.set_appearance_mode("Dark")
    app.mainloop()

if __name__ == "__main__":
    main()
