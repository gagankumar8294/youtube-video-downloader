# YouTube Video & Audio Downloader

A lightweight, ad-free, local web application to fetch and download YouTube videos (up to 4K) or extract high-quality MP3 audio with live download progress bars.

## How to Run on Any Computer

### 1. Install Python
Make sure [Python 3.10+](https://www.python.org/downloads/) is installed and added to PATH.

### 2. Install Required Dependencies
Open a terminal / command prompt in this folder and run:
```bash
pip install -r requirements.txt
```

### 3. Start the Web App
- **Windows**: Double-click `run.bat` (or run `python app.py`)
- **Mac / Linux**: Run `python3 app.py`

### 4. Open in Browser
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

## Features
- Real-time animated progress bar with speed and ETA indicators.
- Automatic FFmpeg detection for merging 1080p / 4K video and audio streams.
- Full aspect ratio support (cinematic widescreen 21:9 & standard 16:9).
- Audio format options (MP3 192kbps, MP3 320kbps, Original M4A).
- Windows UTF-8 encoding safeguard preventing charmap crashes.
