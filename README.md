🎵 YouTube Downloader – Modern UI
By Life • MIT License

A beautiful, modern, Spotify-style YouTube downloader with:

Single video download

Playlist download

Batch URL download

Audio-only mode (mp3/m4a)

Dark/Light themes

Auto-update yt-dlp

No console popups

Full ffmpeg support

100% offline standalone EXE support (PyInstaller)

📸 Screenshots
Modern UI	Playlist	Batch

	
	
✨ Features

✔ Modern CustomTkinter black theme
✔ No console windows
✔ Single, batch, and playlist modes
✔ Drag & drop incoming support
✔ Auto-update yt-dlp
✔ Progress per item (batch/playlist)
✔ Audio extraction (m4a/mp3)
✔ Windows EXE auto-build via GitHub Actions
✔ Feather icon included
✔ MIT license

📦 Install (Run from Source)
pip install customtkinter requests pillow tqdm


Run:

python app/youtube_downloader.py

🖥 Build Standalone EXE (PyInstaller)

Go to:

YouTube-Downloader/app/


Run:

pyinstaller --noconsole --onefile --windowed ^
  --add-data "../ffmpeg;ffmpeg" ^
  --add-data "../ytdlp;ytdlp" ^
  --add-data "resources;resources" ^
  --icon "resources/icon.ico" ^
  youtube_downloader.py


Final EXE will appear in:

app/dist/youtube_downloader.exe


Place it next to:

ffmpeg/
ytdlp/

🚀 Automatic GitHub Release Builds

Every push to main creates:

Windows EXE

Tagged version under "Releases"

Build logs

Workflow is inside:

.github/workflows/build.yml

🧩 Requirements

See requirements.txt.

🎨 Customization

Themes: Dark / Light

Logo: replace app/resources/logo.png

Icon: replace app/resources/icon.ico

ffmpeg auto-download (coming soon)

❤️ Credits

This project uses:

Component	License	Link
yt-dlp	MIT	https://github.com/yt-dlp/yt-dlp

FFmpeg	LGPL/GPL	https://ffmpeg.org

CustomTkinter	MIT	https://github.com/TomSchimansky/CustomTkinter

Pillow	PIL License	https://python-pillow.org

Special thanks to the open-source community.

📄 License

This project is licensed under the MIT License.
See LICENSE for details.

🤝 Contributing

Pull requests welcomed!
See CONTRIBUTING.md.

🧭 Project Roadmap

Future releases will include:

Drag & drop support

Built-in ffmpeg updater

Built-in yt-dlp auto setup

System tray mini-downloader

Resume failed downloads

Advanced format selection
