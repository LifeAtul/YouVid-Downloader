import subprocess
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YTDLP = os.path.join(BASE_DIR, "ytdlp", "yt-dlp.exe")

print(f"Checking {YTDLP}")
if os.path.exists(YTDLP):
    try:
        result = subprocess.run([YTDLP, "--version"], capture_output=True, text=True)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
    except Exception as e:
        print(f"Error: {e}")
else:
    print("yt-dlp not found")
