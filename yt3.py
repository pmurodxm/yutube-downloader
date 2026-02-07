import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from PIL import Image, ImageTk  # pip install pillow
import yt_dlp
import threading
import os
import io
import requests

class GuiLogger:
    def __init__(self, text_widget):
        self.text = text_widget

    def debug(self, msg):
        if not msg.startswith('[debug] '):
            self.info(msg)

    def info(self, msg):
        self.text_insert(f"{msg}\n")

    def warning(self, msg):
        self.text_insert(f"[WARNING] {msg}\n", "warning")

    def error(self, msg):
        self.text_insert(f"[ERROR] {msg}\n", "error")

    def text_insert(self, text, tag=None):
        self.text.configure(state='normal')
        self.text.insert(tk.END, text, tag)
        self.text.see(tk.END)
        self.text.configure(state='disabled')


class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader v3")
        self.root.geometry("680x680")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 11), padding=8)
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=10, background="#7c3aed")
        style.map("Accent.TButton", background=[("active", "#9f7aea")])
        style.configure("TLabel", background="#1e1e2e", foreground="#e0e0ff", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#c084fc")
        style.configure("TProgressbar", thickness=24)
        style.configure("Horizontal.TProgressbar", troughcolor="#2d2d44", background="#a78bfa")

        self.ydl = None
        self.download_thread = None
        self.current_percent = 0
        self.thumbnail_label = None
        self.thumbnail_img = None

        self.create_widgets()

    def create_widgets(self):
        header_frame = ttk.Frame(self.root, padding=15)
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text="YouTube Downloader v3", style="Header.TLabel").pack()

        url_frame = ttk.Frame(self.root, padding=(15, 5))
        url_frame.pack(fill=tk.X)

        ttk.Label(url_frame, text="Link:").pack(side=tk.LEFT, padx=(0, 8))
        self.entry_url = ttk.Entry(url_frame, font=("Segoe UI", 11))
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        ttk.Button(url_frame, text="Boshlash", style="Accent.TButton",
                   command=self.start_process).pack(side=tk.RIGHT, padx=5)

        # Thumbnail joyi (video yuz rasmi)
        thumb_frame = ttk.Frame(self.root, padding=10)
        thumb_frame.pack(pady=8)
        self.thumbnail_label = ttk.Label(thumb_frame, text="Thumbnail yuklanmoqda...", background="#111827", foreground="#9ca3af")
        self.thumbnail_label.pack()

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=640, mode="determinate",
                                        style="Horizontal.TProgressbar")
        self.progress.pack(pady=(5, 5))

        self.percent_label = ttk.Label(self.root, text="0%", font=("Segoe UI", 10, "bold"), foreground="#a78bfa")
        self.percent_label.pack()

        # Log oynasi – endi kichikroq
        log_frame = ttk.Frame(self.root, padding=(15, 5))
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=7, state='disabled',  # ← 7 qator
                                                  font=("Consolas", 9), bg="#111827", fg="#d1d5db",
                                                  insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_config("warning", foreground="#fbbf24")
        self.log_text.tag_config("error",   foreground="#f87171")
        self.log_text.tag_config("success", foreground="#6ee7b7")
        self.log_text.tag_config("info",    foreground="#93c5fd")

        self.status_var = tk.StringVar(value="Linkni kiriting...")
        status = ttk.Label(self.root, textvariable=self.status_var, relief=tk.FLAT,
                           anchor=tk.W, background="#111827", foreground="#9ca3af", padding=8)
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, msg, tag="info"):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, msg + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def update_progress(self, percent):
        try:
            p = float(percent.strip('%').replace(',', '.')) if percent.strip('%') else 0
            self.current_percent = p
            self.progress['value'] = p
            self.percent_label.config(text=f"{percent.strip()}")
            self.root.update_idletasks()
        except:
            pass

    def show_thumbnail(self, thumb_url):
        try:
            response = requests.get(thumb_url, timeout=8)
            response.raise_for_status()
            img_data = response.content
            img = Image.open(io.BytesIO(img_data))
            img = img.resize((320, 180), Image.LANCZOS)  # YouTube thumbnail o'lchami ~16:9
            self.thumbnail_img = ImageTk.PhotoImage(img)
            self.thumbnail_label.config(image=self.thumbnail_img, text="")
        except Exception as e:
            self.thumbnail_label.config(text=f"Thumbnail yuklanmadi\n({str(e)})")

    def start_process(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Xato", "Linkni kiriting!")
            return

        self.log("Link qabul qilindi → " + url, "success")
        self.status_var.set("Ma'lumot olinmoqda...")
        self.progress['value'] = 0
        self.percent_label.config(text="0%")
        self.thumbnail_label.config(image='', text="Thumbnail yuklanmoqda...")

        # Thumbnail + info olish uchun alohida thread
        threading.Thread(target=self.fetch_info_and_thumb, args=(url,), daemon=True).start()

    def fetch_info_and_thumb(self, url):
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                thumb_url = info.get('thumbnail') or info.get('thumbnails', [{}])[0].get('url')
                if thumb_url:
                    self.root.after(0, self.show_thumbnail, thumb_url)
                else:
                    self.root.after(0, lambda: self.thumbnail_label.config(text="Thumbnail topilmadi"))

            self.root.after(0, lambda: self.ask_format(url))
        except Exception as e:
            self.root.after(0, lambda: [
                self.log(f"Info olishda xato: {str(e)}", "error"),
                self.thumbnail_label.config(text="Video ma'lumoti olinmadi"),
                self.status_var.set("Xato yuz berdi")
            ])

    def ask_format(self, url):
        win = tk.Toplevel(self.root)
        win.title("Nima yuklaymiz?")
        win.geometry("420x260")
        win.configure(bg="#1e1e2e")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Tanlang:", style="Header.TLabel").pack(pady=15)

        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.pack()

        ttk.Button(btn_frame, text="🎥 Video (mp4)", style="Accent.TButton", width=25,
                   command=lambda: [win.destroy(), self.ask_video_quality(url)]).pack(pady=8)

        ttk.Button(btn_frame, text="🎵 Audio (mp3)", style="Accent.TButton", width=25,
                   command=lambda: [win.destroy(), self.ask_folder_and_download(url, "audio", None)]).pack(pady=8)

        ttk.Button(btn_frame, text="Bekor qilish", command=win.destroy).pack(pady=10)

    def ask_video_quality(self, url):
        win = tk.Toplevel(self.root)
        win.title("Video sifatini tanlang")
        win.geometry("420x300")
        win.configure(bg="#1e1e2e")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Sifatni tanlang:", style="Header.TLabel").pack(pady=20)

        qualities = ["360p", "480p", "720p", "1080p", "Eng yaxshisi"]
        self.selected_quality = tk.StringVar(value="720p")

        for q in qualities:
            rb = ttk.Radiobutton(win, text=q, variable=self.selected_quality, value=q)
            rb.pack(pady=4, anchor="w", padx=40)

        def confirm():
            win.destroy()
            self.ask_folder_and_download(url, "video", self.selected_quality.get())

        ttk.Button(win, text="Davom etish", style="Accent.TButton", command=confirm).pack(pady=20)
        ttk.Button(win, text="Orqaga", command=win.destroy).pack()

    def ask_folder_and_download(self, url, mode, quality=None):
        title = "Videoni saqlash joyi" if mode == "video" else "Audioni saqlash joyi"
        folder = filedialog.askdirectory(title=title)
        if not folder:
            self.log("Bekor qilindi — papka tanlanmadi", "warning")
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
                height_map = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080, "Eng yaxshisi": None}
                max_h = height_map.get(quality)
                fmt = f'bestvideo[height<={max_h}][ext=mp4]+bestaudio[ext=m4a]' if max_h else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]'
                fmt += '/best[ext=mp4]/best'

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

            self.log("\n✅ Tayyor!", "success")
            self.status_var.set("Yuklash yakunlandi ✓")
            self.root.after(0, self.update_progress, "100%")

        except Exception as e:
            self.log(f"\n❌ Xato: {str(e)}", "error")
            self.status_var.set("Xato yuz berdi")

    def my_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%')
            self.root.after(0, self.update_progress, percent)
        elif d['status'] == 'finished':
            self.root.after(0, lambda: self.log("Fayl yuklandi → birlashtirilmoqda...", "success"))


if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()