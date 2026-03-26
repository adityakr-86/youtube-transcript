import streamlit as st
import subprocess
import time
import random
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from io import StringIO

# ==============================
# CONFIG
# ==============================
BATCH_SIZE = 20
REQUEST_DELAY_MIN = 3
REQUEST_DELAY_MAX = 6
REQUESTS_BEFORE_COOLDOWN = 12
COOLDOWN_TIME = 60
MAX_RETRIES = 3

# ==============================
# GET VIDEOS
# ==============================
def get_videos(playlist_url):
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--print", "%(id)s||%(title)s", playlist_url],
        capture_output=True,
        text=True
    )

    lines = result.stdout.strip().split("\n")
    return [tuple(line.split("||", 1)) for line in lines if "||" in line]

# ==============================
# FETCH TRANSCRIPT
# ==============================
def fetch_transcript(video_id, ytt):
    transcript_list = ytt.list(video_id)

    for langs in [['en', 'en-GB', 'en-US'], ['hi'], ['hi', 'en']]:
        try:
            return transcript_list.find_transcript(langs).fetch()
        except:
            pass

    for t in transcript_list:
        return t.fetch()

    return None

# ==============================
# RETRY LOGIC
# ==============================
def fetch_with_retry(video_id, ytt):
    for attempt in range(MAX_RETRIES):
        try:
            return fetch_transcript(video_id, ytt)
        except Exception as e:
            msg = str(e).lower()

            if "blocking requests" in msg:
                wait = 120 + random.uniform(5, 15)
                time.sleep(wait)
            else:
                wait = (2 ** attempt) + random.uniform(2, 5)
                time.sleep(wait)

    return None

# ==============================
# PROCESS
# ==============================
def process_playlist(playlist_url):
    videos = get_videos(playlist_url)
    ytt = YouTubeTranscriptApi()
    formatter = TextFormatter()

    output = StringIO()

    total = len(videos)
    progress = st.progress(0)
    status = st.empty()

    request_count = 0

    for i, (vid, title) in enumerate(videos, start=1):
        status.text(f"Processing {i}/{total}: {title}")

        transcript = fetch_with_retry(vid, ytt)

        if transcript:
            formatted = formatter.format_transcript(transcript)

            output.write("=" * 80 + "\n")
            output.write(f"TITLE: {title}\n")
            output.write(f"VIDEO ID: {vid}\n")
            output.write("=" * 80 + "\n\n")
            output.write(formatted + "\n\n\n")

        request_count += 1

        # Delay
        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        # Cooldown
        if request_count % REQUESTS_BEFORE_COOLDOWN == 0:
            status.text("Cooling down...")
            time.sleep(COOLDOWN_TIME)

        progress.progress(i / total)

    return output.getvalue()

# ==============================
# UI
# ==============================
st.set_page_config(page_title="YouTube Transcript Extractor", layout="centered")

st.title("📺 YouTube Playlist → Transcript Downloader")

playlist_url = st.text_input("Enter Playlist URL")

if st.button("Generate Transcript"):
    if playlist_url:
        with st.spinner("Processing... This may take time ⏳"):
            result = process_playlist(playlist_url)

        st.success("Done!")

        st.download_button(
            label="📥 Download Transcript",
            data=result,
            file_name="transcripts.txt",
            mime="text/plain"
        )
    else:
        st.warning("Please enter a playlist URL")
