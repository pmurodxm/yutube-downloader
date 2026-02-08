# main.py
# YouTube Downloader - GUI bilan, auto-update, thumbnail, icon, Telegram info
# GitHub: https://github.com/pmurodxm/yutube-downloader
# Telegram yangiliklari: @CodeDrop_py

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from PIL import Image, ImageTk
import yt_dlp
import threading
import os
import sys
import io
import requests
import tempfile
import shutil
import subprocess

# ────────────────────────────────────────────────
# Sozlamalar
# ────────────────────────────────────────────────
CURRENT_VERSION = "1.0.0"                     # Har yangi release da o'zgartiring (masalan 1.1.0)
GITHUB_REPO = "pmurodxm/yutube-downloader"
TELEGRAM_CHANNEL = "@CodeDrop_py"

# Exe rejimida BASE_PATH ni to'g'ri topish
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_PATH = sys._MEIPASS
else:
    BASE_PATH = os.path.abspath(os.path.dirname(__file__))

# ffmpeg yo'li (PyInstaller bilan qo'shilgan bo'lsa)
FFMPEG_PATH = os.path.join(BASE_PATH, "bin", "ffmpeg.exe")
if os.path.exists(FFMPEG_PATH):
    os.environ["FFMPEG_LOCATION"] = FFMPEG_PATH


class GuiLogger:
    def __init__(self, text_widget):
        self.text = text_widget

    def debug(self, msg):
        if not msg.startswith('[debug] '):
            self.info(msg)

    def info(self, msg):
        self._insert(f"{msg}\n")

    def warning(self, msg):
        self._insert(f"[WARNING] {msg}\n", "warning")

    def error(self, msg):
        self._insert(f"[ERROR] {msg}\n", "error")

    def _insert(self, text, tag=None):
        self.text.configure(state='normal')
        self.text.insert(tk.END, text, tag)
        self.text.see(tk.END)
        self.text.configure(state='disabled')


class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"YouTube Downloader v{CURRENT_VERSION}")
        self.root.geometry("720x740")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass  # icon topilmasa xato chiqmasin

        self._setup_style()
        self.thumbnail_img = None
        self.download_thread = None

        self.create_widgets()
        self.check_update_on_start()

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TButton", font=("Segoe UI", 11), padding=8)
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=10)
        style.map("Accent.TButton", background=[("!active", "#7c3aed"), ("active", "#9f7aea")])

        # Asosiy matn ranglari
        style.configure("Dark.TLabel",     background="#1e1e2e", foreground="#e0e0ff", font=("Segoe UI", 10))
        style.configure("Thumb.TLabel",    background="#111827", foreground="#9ca3af")
        style.configure("Percent.TLabel",  background="#1e1e2e", foreground="#a78bfa", font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel",   background="#111827", foreground="#9ca3af")

        style.configure("Header.TLabel",   font=("Segoe UI", 18, "bold"), foreground="#c084fc")
        style.configure("Horizontal.TProgressbar", thickness=24, troughcolor="#2d2d44", background="#a78bfa")

    def create_widgets(self):
        # Header + Telegram info
        header_frame = ttk.Frame(self.root, padding=15)
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text=f"YouTube Downloader v{CURRENT_VERSION}", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(header_frame, text=f"  Yangiliklar: {TELEGRAM_CHANNEL}", style="Dark.TLabel").pack(side=tk.RIGHT, padx=10)

        # URL input
        url_frame = ttk.Frame(self.root, padding=(15, 5))
        url_frame.pack(fill=tk.X)
        ttk.Label(url_frame, text="YouTube link:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        self.entry_url = ttk.Entry(url_frame, font=("Segoe UI", 11))
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(url_frame, text="Boshlash", style="Accent.TButton", command=self.start_process).pack(side=tk.RIGHT, padx=5)

        # Thumbnail (height va width olib tashlandi, wraplength qo'shildi)
        thumb_frame = ttk.Frame(self.root, padding=10)
        thumb_frame.pack(pady=8)
        
        self.thumbnail_label = ttk.Label(thumb_frame, 
                                        text="Video preview yuklanmoqda...", 
                                        style="Thumb.TLabel",
                                        wraplength=360,          # matn uzun bo'lsa o'raladi
                                        justify="center")
        self.thumbnail_label.pack()

        # Progress bar + percent
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=660, mode="determinate")
        self.progress.pack(pady=(5, 5))
        self.percent_label = ttk.Label(self.root, text="0%", style="Percent.TLabel")
        self.percent_label.pack()

        # Log oynasi
        log_frame = ttk.Frame(self.root, padding=(15, 5))
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state='disabled',
                                                  font=("Consolas", 9), bg="#111827", fg="#d1d5db",
                                                  insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_config("warning", foreground="#fbbf24")
        self.log_text.tag_config("error",   foreground="#f87171")
        self.log_text.tag_config("success", foreground="#6ee7b7")
        self.log_text.tag_config("info",    foreground="#93c5fd")

        # Status bar
        self.status_var = tk.StringVar(value="Havolani kiriting va Boshlash tugmasini bosing")
        status = ttk.Label(self.root, 
                           textvariable=self.status_var, 
                           style="Status.TLabel",
                           anchor=tk.W, 
                           padding=8)
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, msg, tag="info"):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, msg + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def update_progress(self, percent):
        try:
            p = float(percent.strip('%').replace(',', '.'))
            self.progress['value'] = p
            self.percent_label.config(text=f"{percent.strip()}")
            self.root.update_idletasks()
        except:
            pass

    def show_thumbnail(self, thumb_url):
        try:
            response = requests.get(thumb_url, timeout=8)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content))
            img = img.resize((360, 202), Image.Resampling.LANCZOS)
            self.thumbnail_img = ImageTk.PhotoImage(img)
            self.thumbnail_label.config(image=self.thumbnail_img, text="")
        except Exception as e:
            self.thumbnail_label.config(text=f"Preview yuklanmadi\n({str(e)})")

    def start_process(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Xato", "Iltimos, YouTube havolasini kiriting!")
            return

        self.log("Havola qabul qilindi → " + url, "success")
        self.status_var.set("Ma'lumot olinmoqda...")
        self.progress['value'] = 0
        self.percent_label.config(text="0%")
        self.thumbnail_label.config(image='', text="Preview yuklanmoqda...")

        threading.Thread(target=self.fetch_info_and_thumb, args=(url,), daemon=True).start()

    def fetch_info_and_thumb(self, url):
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                thumb_url = info.get('thumbnail') or (info.get('thumbnails') or [{}])[0].get('url', '')
                if thumb_url:
                    self.root.after(0, self.show_thumbnail, thumb_url)
                else:
                    self.root.after(0, lambda: self.thumbnail_label.config(text="Rasm topilmadi"))

            self.root.after(0, lambda: self.ask_format(url))
        except Exception as e:
            self.root.after(0, lambda: [
                self.log(f"Ma'lumot olishda xato: {str(e)}", "error"),
                self.thumbnail_label.config(text="Video ma'lumotlari olinmadi"),
                self.status_var.set("Xatolik yuz berdi")
            ])

    def ask_format(self, url):
        win = tk.Toplevel(self.root)
        win.title("Nima yuklaymiz?")
        win.geometry("440x280")
        win.configure(bg="#1e1e2e")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Tanlang:", style="Header.TLabel").pack(pady=20)

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="🎥 Video (mp4)", style="Accent.TButton", width=25,
                   command=lambda: [win.destroy(), self.ask_video_quality(url)]).pack(pady=10)

        ttk.Button(btn_frame, text="🎵 Audio (mp3)", style="Accent.TButton", width=25,
                   command=lambda: [win.destroy(), self.ask_folder_and_download(url, "audio", None)]).pack(pady=10)

        ttk.Button(btn_frame, text="Bekor qilish", command=win.destroy).pack(pady=10)

    def ask_video_quality(self, url):
        win = tk.Toplevel(self.root)
        win.title("Sifatni tanlang")
        win.geometry("440x340")
        win.configure(bg="#1e1e2e")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Video sifati:", style="Header.TLabel").pack(pady=20)

        qualities = ["360p", "480p", "720p", "1080p", "Eng yuqori sifat"]
        self.selected_quality = tk.StringVar(value="720p")

        for q in qualities:
            ttk.Radiobutton(win, text=q, variable=self.selected_quality, value=q).pack(pady=6, anchor="w", padx=60)

        def confirm():
            win.destroy()
            self.ask_folder_and_download(url, "video", self.selected_quality.get())

        ttk.Button(win, text="Davom etish", style="Accent.TButton", command=confirm).pack(pady=25)
        ttk.Button(win, text="Orqaga", command=win.destroy).pack()

    def ask_folder_and_download(self, url, mode, quality=None):
        title = "Videoni saqlash joyi" if mode == "video" else "Audioni saqlash joyi"
        folder = filedialog.askdirectory(title=title)
        if not folder:
            self.log("Papka tanlanmadi → bekor qilindi", "warning")
            self.status_var.set("Bekor qilindi")
            return

        self.start_download(url, mode, folder, quality)

    def start_download(self, url, mode, out_folder, quality):
        if self.download_thread and self.download_thread.is_alive():
            self.log("Yuklash allaqachon davom etmoqda...", "warning")
            return

        self.log_text.configure(state='normal')
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state='disabled')

        self.log(f"→ Yuklash boshlandi ({mode.upper()})", "success")
        if quality:
            self.log(f"Sifat: {quality}", "info")
        self.status_var.set("Yuklanmoqda...")

        self.download_thread = threading.Thread(
            target=self.download_task,
            args=(url, mode, out_folder, quality),
            daemon=True
        )
        self.download_thread.start()

    def download_task(self, url, mode, out_folder, quality):
        try:
            logger = GuiLogger(self.log_text)

            if mode == "video":
                height_map = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080, "Eng yuqori sifat": None}
                max_h = height_map.get(quality)
                fmt = f'bestvideo[height<={max_h}][ext=mp4]+bestaudio[ext=m4a]/best' if max_h else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
                ydl_opts = {
                    'format': fmt,
                    'outtmpl': os.path.join(out_folder, '%(title)s.%(ext)s'),
                    'merge_output_format': 'mp4',
                    'noplaylist': True,
                }
            else:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(out_folder, '%(title)s.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.add_progress_hook(self.my_hook)
                ydl.params['logger'] = logger
                ydl.download([url])

            self.root.after(0, lambda: [
                self.log("\n✅ Yuklash muvaffaqiyatli yakunlandi!", "success"),
                self.status_var.set("Tayyor ✓"),
                self.update_progress("100%")
            ])

        except Exception as e:
            self.root.after(0, lambda: [
                self.log(f"\n❌ Xato: {str(e)}", "error"),
                self.status_var.set("Xatolik yuz berdi")
            ])

    def my_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%')
            self.root.after(0, self.update_progress, percent)
        elif d['status'] == 'finished':
            self.root.after(0, lambda: self.log("Fayl yuklandi → post-processing...", "success"))

    # ────────────────────────────────────────────────
    # Auto-update funksiyalari
    # ────────────────────────────────────────────────
    def check_update_on_start(self):
        threading.Thread(target=self._check_for_update, daemon=True).start()

    def _check_for_update(self):
        try:
            response = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", timeout=10)
            response.raise_for_status()
            data = response.json()
            latest_tag = data['tag_name'].lstrip('v')
            if self._version_tuple(latest_tag) > self._version_tuple(CURRENT_VERSION):
                asset = next((a for a in data['assets'] if a['name'].lower().endswith('.exe')), None)
                if asset:
                    download_url = asset['browser_download_url']
                    self.root.after(0, lambda: self._show_update_prompt(latest_tag, download_url))
        except:
            pass

    def _version_tuple(self, v):
        return tuple(map(int, v.split('.')))

    def _show_update_prompt(self, new_version, download_url):
        if messagebox.askyesno(
            "Yangilanish mavjud",
            f"Yangi versiya v{new_version} chiqdi!\n\n"
            f"Yangilashni hozir boshlaymizmi?\n\n"
            f"Yangiliklar va yangi versiyalar: {TELEGRAM_CHANNEL}"
        ):
            self._perform_update(download_url)

    def _perform_update(self, download_url):
        try:
            temp_dir = tempfile.mkdtemp()
            new_exe = os.path.join(temp_dir, "YouTubeDownloader_new.exe")

            self.log("Yangilanish yuklanmoqda...", "info")

            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(new_exe, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)

            bat_path = os.path.join(temp_dir, "update.bat")
            current_exe = sys.executable if getattr(sys, 'frozen', False) else __file__

            with open(bat_path, 'w', encoding='utf-8') as bat:
                bat.write(f"""@echo off
timeout /t 3 >nul
taskkill /f /im "{os.path.basename(current_exe)}" >nul 2>&1
move /y "{new_exe}" "{current_exe}"
start "" "{current_exe}"
rmdir /s /q "{temp_dir}"
del "%~f0"
""")

            subprocess.Popen(['cmd.exe', '/c', bat_path], creationflags=subprocess.DETACHED_PROCESS)
            self.root.quit()

        except Exception as e:
            messagebox.showerror("Yangilash xatosi", f"Yangilash muvaffaqiyatsiz: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()