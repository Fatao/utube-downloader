import sys
import os
import yt_dlp
import requests
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QComboBox, QFrame, 
                             QMessageBox, QFileDialog, QProgressBar)
from PySide6.QtCore import Qt, QThread, Signal
# Added QIcon to imports
from PySide6.QtGui import QPixmap, QImage, QIcon

# Silencing yt-dlp terminal output
class MyLogger:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

class InfoThread(QThread):
    info_received = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            ydl_opts = {
                'quiet': True, 
                'no_warnings': True, 
                'logger': MyLogger(),
                'skip_download': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                duration_sec = info.get('duration', 0)
                mins, secs = divmod(duration_sec, 60)
                duration_str = f"{mins}:{secs:02d}"
                
                video_id = info.get('id')
                thumb_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                
                data = {
                    'title': info.get('title', 'Unknown Title'),
                    'duration': duration_str,
                    'upload_date': info.get('upload_date', 'N/A'),
                    'thumbnail_url': thumb_url,
                    'uploader': info.get('uploader', 'Unknown')
                }
                self.info_received.emit(data)
        except Exception as e:
            self.error_signal.emit(str(e))

class DownloadThread(QThread):
    progress_signal = Signal(float, str)
    finished = Signal(str)
    
    def __init__(self, url, mode, save_path):
        super().__init__()
        self.url = url
        self.mode = mode
        self.save_path = save_path

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            
            if total:
                percentage = (downloaded / total) * 100
                self.progress_signal.emit(percentage, f"Downloading...")
        
        elif d['status'] == 'finished':
            self.progress_signal.emit(100.0, "Download Complete! Finalizing...")

    def run(self):
        try:
            common_opts = {
                'outtmpl': os.path.join(self.save_path, '%(title)s.%(ext)s'),
                'progress_hooks': [self.progress_hook],
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
                'logger': MyLogger(),
            }

            if "Video" in self.mode:
                ydl_opts = {**common_opts, 'format': 'bestvideo+bestaudio/best'}
            else:
                ydl_opts = {
                    **common_opts,
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])

            self.finished.emit("Success: Download Finished!")
        except Exception as e:
            self.finished.emit(f"Error: {str(e)}")

class YouTubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader Pro")
        self.setFixedSize(550, 620)
        
        # --- SET ICON LOGIC ---
        # This looks for icon.png in the same folder as this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        # ----------------------

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        title_label = QLabel("YouTube Downloader")
        title_label.setObjectName("mainTitle")
        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Input Section
        input_frame = QFrame()
        input_frame.setObjectName("groupFrame")
        input_layout = QVBoxLayout(input_frame)
        input_layout.addWidget(QLabel("Video URL:"))
        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube link here...")
        self.url_input.textChanged.connect(self.on_url_changed)
        paste_btn = QPushButton("Paste")
        paste_btn.clicked.connect(lambda: self.url_input.setText(QApplication.clipboard().text()))
        url_row.addWidget(self.url_input)
        url_row.addWidget(paste_btn)
        input_layout.addLayout(url_row)
        main_layout.addWidget(input_frame)

        # Preview Section
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("previewFrame")
        self.preview_frame.setMinimumHeight(120)
        preview_layout = QHBoxLayout(self.preview_frame)
        self.thumb_label = QLabel("Thumbnail")
        self.thumb_label.setFixedSize(200, 120)
        self.thumb_label.setStyleSheet("background: #000; color: #555; border-radius: 4px;")
        self.thumb_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.thumb_label)

        info_text_layout = QVBoxLayout()
        self.video_title = QLabel("Video details will appear here...")
        self.video_title.setWordWrap(True)
        self.video_title.setStyleSheet("font-weight: bold; color: #333;")
        self.video_meta = QLabel("")
        self.video_meta.setStyleSheet("color: #666; font-size: 11px;")
        info_text_layout.addWidget(self.video_title)
        info_text_layout.addWidget(self.video_meta)
        info_text_layout.addStretch()
        preview_layout.addLayout(info_text_layout)
        main_layout.addWidget(self.preview_frame)

        # Path Section
        path_frame = QFrame()
        path_frame.setObjectName("groupFrame")
        path_layout = QVBoxLayout(path_frame)
        path_layout.addWidget(QLabel("Save To Folder:"))
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(os.path.join(os.path.expanduser("~"), "Downloads"))
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)
        path_row.addWidget(self.path_input)
        path_row.addWidget(browse_btn)
        path_layout.addLayout(path_row)
        main_layout.addWidget(path_frame)

        # Settings Section
        settings_frame = QFrame()
        settings_frame.setObjectName("groupFrame")
        settings_layout = QHBoxLayout(settings_frame)
        settings_layout.addWidget(QLabel("Format:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Video (Best Quality)", "Audio (High Quality MP3)"])
        settings_layout.addWidget(self.mode_combo)
        self.download_btn = QPushButton("Start Download")
        self.download_btn.setObjectName("downloadBtn")
        self.download_btn.clicked.connect(self.start_download)
        settings_layout.addWidget(self.download_btn)
        main_layout.addWidget(settings_frame)

        # Status & Progress
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        main_layout.addWidget(self.progress_bar)

    def on_url_changed(self):
        url = self.url_input.text().strip()
        if "youtube.com" in url or "youtu.be" in url:
            self.video_title.setText("Fetching video info...")
            self.info_thread = InfoThread(url)
            self.info_thread.info_received.connect(self.update_video_info)
            self.info_thread.start()

    def update_video_info(self, data):
        self.video_title.setText(data['title'])
        d = data['upload_date']
        f_date = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d
        self.video_meta.setText(f"Duration: {data['duration']} | Uploaded: {f_date}\nChannel: {data['uploader']}")
        try:
            resp = requests.get(data['thumbnail_url'], timeout=5)
            img = QImage()
            img.loadFromData(resp.content)
            self.thumb_label.setPixmap(QPixmap.fromImage(img).scaled(self.thumb_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        except:
            self.thumb_label.setText("No Preview")

    def browse_folder(self):
        dir = QFileDialog.getExistingDirectory(self, "Select Folder")
        if dir: self.path_input.setText(dir)

    def start_download(self):
        url = self.url_input.text().strip()
        save_path = self.path_input.text().strip()
        if not url: return
        self.download_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.thread = DownloadThread(url, self.mode_combo.currentText(), save_path)
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def update_progress(self, percent, status_text):
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(status_text)

    def on_finished(self, message):
        self.download_btn.setEnabled(True)
        self.status_label.setText("Idle")
        QMessageBox.information(self, "Status", message)

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget { background-color: #E0E0E0; font-family: 'Segoe UI'; font-size: 12; }
            #mainTitle { font-size: 24px; color: #cc0000; font-weight: bold; margin: 10px; }
            #groupFrame, #previewFrame { background-color: #F5F5F5; border: 1px solid #C0C0C0; padding: 10px; border-radius: 4px; }
            #previewFrame { background-color: #FFFFFF; }
            QLineEdit { background: white; border: 1px solid #999; padding: 5px; border-radius: 3px; }
            QPushButton { background: #E1E1E1; border: 1px solid #ADADAD; padding: 6px 15px; }
            #downloadBtn { background: #0078D7; color: white; font-weight: bold; border: none; min-width: 120px; }
            #downloadBtn:hover { background: #005A9E; }
            QProgressBar { border: 1px solid #999; border-radius: 3px; text-align: center; background: white; height: 20px; }
            QProgressBar::chunk { background-color: #0078D7; }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec())