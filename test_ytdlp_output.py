import os
import subprocess
import sys

# Path setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YTDLP = os.path.join(BASE_DIR, "ytdlp", "yt-dlp.exe")
FFMPEG = os.path.join(BASE_DIR, "ffmpeg", "ffmpeg.exe")

# Test URL (short video)
URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw" # Me at the zoo (19 seconds)

def run_test():
    if not os.path.exists(YTDLP):
        print(f"Error: yt-dlp not found at {YTDLP}")
        return
    if not os.path.exists(FFMPEG):
        print(f"Error: ffmpeg not found at {FFMPEG}")
        return

    output_template = os.path.join(BASE_DIR, "test_download", "%(title)s.%(ext)s")
    
    cmd = [
        YTDLP, 
        "-f", "bestvideo+bestaudio", 
        "--ffmpeg-location", FFMPEG, 
        "--merge-output-format", "mp4", 
        "-o", output_template, 
        URL
    ]

    print(f"Running command: {' '.join(cmd)}")
    
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True, 
        bufsize=1
    )

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            print(f"OUTPUT: {line.strip()}")

    rc = process.poll()
    print(f"Finished with code {rc}")

if __name__ == "__main__":
    run_test()
