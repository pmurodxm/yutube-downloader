import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import yt_dlp
import threading
import sys
import os

# ----------------- yt-dlp Logger -----------------
class GuiLogger:
    def __init__(self, text_widget):
        self.text = text_widget

    def debug(self, msg):
        if msg.startswith('[debug] '):
            self.text_insert(f"{msg}\n")
        else:
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


# ----------------- Asosiy oynani yaratish -----------------
class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader (yt-dlp)")
        self.root.geometry("720x580")
        self.root.resizable(True, True)

        self.ydl = None
        self.download_thread = None

        self.create_widgets()

    def create_widgets(self):
        # ----------------- Link kiritish -----------------
        frame_link = ttk.Frame(self.root, padding=10)
        frame_link.pack(fill=tk.X)

        ttk.Label(frame_link, text="YouTube link:").pack(side=tk.LEFT, padx=5)
        self.entry_url = ttk.Entry(frame_link)
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(frame_link, text="Yuklashni boshlash", command=self.start_process).pack(side=tk.LEFT, padx=5)

        # ----------------- Log oynasi -----------------
        self.log_text = scrolledtext.ScrolledText(self.root, height=18, state='disabled', font=("Consolas", 10))
        self.log_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Ranglar qo'shamiz
        self.log_text.tag_config("warning", foreground="orange")
        self.log_text.tag_config("error",   foreground="red")
        self.log_text.tag_config("success", foreground="green")

        # ----------------- Status label -----------------
        self.status_var = tk.StringVar(value="Linkni kiriting va \"Yuklashni boshlash\" tugmasini bosing")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, msg, tag=None):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, msg + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def start_process(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Xato", "Iltimos, YouTube linkini kiriting!")
            return

        self.log("Link qabul qilindi: " + url, "success")
        self.status_var.set("Format tanlanmoqda...")

        # Yangi oynada format tanlash
        self.ask_format(url)

    def ask_format(self, url):
        win = tk.Toplevel(self.root)
        win.title("Format tanlash")
        win.geometry("400x180")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Nima yuklab olmoqchisiz?", font=("Segoe UI", 12)).pack(pady=15)

        def choose_video():
            win.destroy()
            self.ask_folder_and_download(url, mode="video")

        def choose_audio():
            win.destroy()
            self.ask_folder_and_download(url, mode="audio")

        ttk.Button(win, text="🎥 Video (mp4)", command=choose_video, width=25).pack(pady=8)
        ttk.Button(win, text="🎵 Faqat audio (mp3)", command=choose_audio, width=25).pack(pady=8)

        ttk.Button(win, text="Bekor qilish", command=win.destroy).pack(pady=10)

    def ask_folder_and_download(self, url, mode):
        if mode == "video":
            folder = filedialog.askdirectory(title="Videoni qayerga saqlaymiz?")
            if not folder:
                self.log("Bekor qilindi — papka tanlanmadi", "warning")
                self.status_var.set("Yuklash bekor qilindi")
                return
            self.start_download(url, mode, folder)
        else:
            # Audio uchun ham papka so‘raymiz (xohlasangiz o‘zgartirsa bo‘ladi)
            folder = filedialog.askdirectory(title="Audio faylni qayerga saqlaymiz?")
            if not folder:
                self.log("Bekor qilindi — papka tanlanmadi", "warning")
                self.status_var.set("Yuklash bekor qilindi")
                return
            self.start_download(url, mode, folder)

    def start_download(self, url, mode, output_folder):
        if self.download_thread and self.download_thread.is_alive():
            self.log("Hozir yuklash jarayoni davom etmoqda...", "warning")
            return

        self.log_text.configure(state='normal')
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state='disabled')

        self.log(f"→ Yuklash boshlandi ({mode.upper()})\n", "success")
        self.status_var.set("Yuklanmoqda... (log oynasiga qarang)")

        self.download_thread = threading.Thread(
            target=self.download_task,
            args=(url, mode, output_folder),
            daemon=True
        )
        self.download_thread.start()

    def download_task(self, url, mode, out_folder):
        try:
            logger = GuiLogger(self.log_text)

            if mode == "video":
                ydl_opts = {
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'outtmpl': os.path.join(out_folder, '%(title)s.%(ext)s'),
                    'merge_output_format': 'mp4',
                    'quiet': False,
                    'no_warnings': False,
                }
            else:  # audio
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(out_folder, '%(title)s.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }

            with yt_dlp.YoutubeDL(ydl_opts) as self.ydl:
                self.ydl.add_progress_hook(self.progress_hook)
                self.ydl.params['logger'] = logger
                self.ydl.download([url])

            self.log("\n✅ Yuklash muvaffaqiyatli yakunlandi!", "success")
            self.status_var.set("Yuklash tugadi ✓")

        except Exception as e:
            self.log(f"\n❌ Xato yuz berdi: {str(e)}", "error")
            self.status_var.set("Xato yuz berdi")

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '?%')
            speed = d.get('_speed_str', '?')
            eta = d.get('_eta_str', '?')
            line = f"{percent}   {speed}   ETA: {eta}"
            self.log_text.configure(state='normal')
            self.log_text.insert(tk.END, line + "\r")
            self.log_text.see(tk.END)
            self.log_text.configure(state='disabled')
        elif d['status'] == 'finished':
            self.log("Fayl yuklandi, post-processing boshlanmoqda...", "success")


# ----------------- Dasturni ishga tushirish -----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()
