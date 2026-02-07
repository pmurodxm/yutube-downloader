import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import yt_dlp
import threading
import os

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
        self.root.title("YouTube Downloader")
        self.root.geometry("680x620")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        # Modern style
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

        self.create_widgets()

    def create_widgets(self):
        # Header
        header_frame = ttk.Frame(self.root, padding=15)
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text="YouTube Downloader", style="Header.TLabel").pack()

        # URL input + button
        url_frame = ttk.Frame(self.root, padding=(15, 5))
        url_frame.pack(fill=tk.X)

        ttk.Label(url_frame, text="Link:").pack(side=tk.LEFT, padx=(0, 8))
        self.entry_url = ttk.Entry(url_frame, font=("Segoe UI", 11))
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        download_btn = ttk.Button(url_frame, text="Yuklashni boshlash", style="Accent.TButton",
                                 command=self.start_process)
        download_btn.pack(side=tk.RIGHT, padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=640, mode="determinate",
                                       style="Horizontal.TProgressbar")
        self.progress.pack(pady=(15, 5))

        self.percent_label = ttk.Label(self.root, text="0%", font=("Segoe UI", 10, "bold"), foreground="#a78bfa")
        self.percent_label.pack()

        # Log area (ixcham)
        log_frame = ttk.Frame(self.root, padding=15)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state='disabled',
                                                 font=("Consolas", 9), bg="#111827", fg="#d1d5db",
                                                 insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Tags for coloring
        self.log_text.tag_config("warning", foreground="#fbbf24")
        self.log_text.tag_config("error",   foreground="#f87171")
        self.log_text.tag_config("success", foreground="#6ee7b7")
        self.log_text.tag_config("info",    foreground="#93c5fd")

        # Status bar
        self.status_var = tk.StringVar(value="Linkni kiriting va yuklashni boshlang")
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
            p = float(percent.strip('%')) if percent.strip('%').replace('.', '').isdigit() else 0
            self.current_percent = p
            self.progress['value'] = p
            self.percent_label.config(text=f"{percent.strip()}")
            self.root.update_idletasks()
        except:
            pass

    def start_process(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Xato", "YouTube linkini kiriting!")
            return

        self.log("Link qabul qilindi → " + url, "success")
        self.status_var.set("Format tanlanmoqda...")
        self.progress['value'] = 0
        self.percent_label.config(text="0%")

        self.ask_format(url)

    def ask_format(self, url):
        win = tk.Toplevel(self.root)
        win.title("Nima yuklaymiz?")
        win.geometry("420x220")
        win.configure(bg="#1e1e2e")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Tanlang:", style="Header.TLabel").pack(pady=20)

        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.pack()

        ttk.Button(btn_frame, text="🎥 Video (mp4)", style="Accent.TButton", width=20,
                  command=lambda: [win.destroy(), self.ask_folder_and_download(url, "video")]).pack(pady=10)

        ttk.Button(btn_frame, text="🎵 Audio (mp3)", style="Accent.TButton", width=20,
                  command=lambda: [win.destroy(), self.ask_folder_and_download(url, "audio")]).pack(pady=5)

        ttk.Button(btn_frame, text="Bekor qilish", command=win.destroy).pack(pady=15)

    def ask_folder_and_download(self, url, mode):
        title = "Videoni saqlash joyi" if mode == "video" else "Audioni saqlash joyi"
        folder = filedialog.askdirectory(title=title)
        if not folder:
            self.log("Bekor qilindi — papka tanlanmadi", "warning")
            self.status_var.set("Yuklash bekor qilindi")
            self.progress['value'] = 0
            self.percent_label.config(text="0%")
            return

        self.start_download(url, mode, folder)

    def start_download(self, url, mode, out_folder):
        if self.download_thread and self.download_thread.is_alive():
            self.log("Yuklash allaqachon davom etmoqda...", "warning")
            return

        self.log_text.configure(state='normal')
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state='disabled')

        self.log(f"→ Yuklash boshlandi ({mode.upper()})", "success")
        self.status_var.set("Yuklanmoqda...")

        self.download_thread = threading.Thread(
            target=self.download_task,
            args=(url, mode, out_folder),
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

            self.log("\n✅ Yuklash muvaffaqiyatli yakunlandi!", "success")
            self.status_var.set("Tayyor ✓")
            self.update_progress("100%")

        except Exception as e:
            self.log(f"\n❌ Xato: {str(e)}", "error")
            self.status_var.set("Xato yuz berdi")

    def my_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%')
            self.root.after(0, self.update_progress, percent)
        elif d['status'] == 'finished':
            self.root.after(0, lambda: self.log("Fayl yuklandi → post-processing...", "success"))


if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()