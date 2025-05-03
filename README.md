
# 🎵 Video & Audio Downloader Web App

A lightweight Flask-based web application to download audio or video content from YouTube, SoundCloud, and Vimeo. Supports quality selection, media validation, and safe downloading.

---

## 🔧 Features

- ✅ URL validation and preview
- 🎶 Audio download as MP3 (320kbps)
- 🎥 Video download up to 1080p
- 🧠 Smart media probing with `ffprobe`
- 🗂️ Auto-sanitized filenames
- 💾 File size limit enforcement (500MB default)
- ⚠️ Graceful error handling

---

## 🚀 Usage

1. **Install dependencies**:

```bash
pip install -r requirements.txt
````

2. **Ensure FFmpeg is installed**:

You need `ffmpeg` and `ffprobe` in your system path.

* On Linux: `sudo apt install ffmpeg`
* On macOS: `brew install ffmpeg`
* On Windows: [Download here](https://ffmpeg.org/download.html)

3. **Run the app**:

```bash
python app.py
```

4. **Access it**:

Open your browser and visit [http://localhost:5000](http://localhost:5000)

---

## 📂 Folder Structure

```
.
├── app.py
├── templates/
│   ├── index.html
│   └── error.html
├── requirements.txt
└── README.md
```

---

## 📦 Requirements

* Python 3.7+
* Flask
* yt-dlp
* FFmpeg (external dependency)

---

## 🔐 Notes

* This tool enforces domain whitelisting (YouTube, SoundCloud, Vimeo).
* Downloads exceeding 500MB are rejected by default.

---

## 📜 License

MIT License. Free to use and modify.

````
