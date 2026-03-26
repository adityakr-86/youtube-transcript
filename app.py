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
HARD_BLOCK_SLEEP = 120

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
                time.sleep(HARD_BLOCK_SLEEP + random.uniform(5, 10))
            else:
                time.sleep((2 ** attempt) + random.uniform(2, 5))

    return None

# ==============================
# PROCESS RANGE
# ==============================
def process_range(videos, start_idx, end_idx):
    ytt = YouTubeTranscriptApi()
    formatter = TextFormatter()

    selected_videos = videos[start_idx:end_idx]

    batches = [
        selected_videos[i:i + BATCH_SIZE]
        for i in range(0, len(selected_videos), BATCH_SIZE)
    ]

    progress = st.progress(0)
    status = st.empty()
    log_placeholder = st.empty()

    logs = []
    total = len(selected_videos)
    processed = 0

    batch_outputs = []

    for batch_num, batch in enumerate(batches, start=1):
        batch_buffer = StringIO()
        request_count = 0

        for vid, title in batch:
            processed += 1
            status.text(f"Processing {processed}/{total}: {title}")

            transcript = fetch_with_retry(vid, ytt)

            if transcript:
                formatted = formatter.format_transcript(transcript)

                batch_buffer.write("=" * 80 + "\n")
                batch_buffer.write(f"TITLE: {title}\n")
                batch_buffer.write(f"VIDEO ID: {vid}\n")
                batch_buffer.write("=" * 80 + "\n\n")
                batch_buffer.write(formatted + "\n\n\n")

                msg = f"{processed:03d}. ✅ {title}"
            else:
                msg = f"{processed:03d}. ❌ {title}"

            logs.append(msg)

            # ✅ Clean log UI
            log_text = "### 📜 Processing Log\n\n" + "\n\n".join(logs[-15:])
            log_placeholder.markdown(log_text)

            request_count += 1

            # Delay between requests
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

            # Cooldown
            if request_count % REQUESTS_BEFORE_COOLDOWN == 0:
                logs.append("🧊 Cooling down...")
                log_placeholder.markdown(
                    "### 📜 Processing Log\n\n" + "\n\n".join(logs[-15:])
                )
                time.sleep(COOLDOWN_TIME)

            progress.progress(processed / total)

        # Save batch output
        batch_outputs.append((batch_num, batch_buffer.getvalue()))

    return batch_outputs

# ==============================
# UI
# ==============================
st.set_page_config(page_title="YouTube Transcript Extractor", layout="centered")

st.title("📺 YouTube Playlist → Transcript Downloader")
st.info("⚠️ Large playlists may take time due to YouTube rate limits.")

playlist_url = st.text_input("Enter Playlist URL")

# Session state
if "videos" not in st.session_state:
    st.session_state.videos = None

# ==============================
# FETCH PLAYLIST
# ==============================
if st.button("🔍 Fetch Playlist"):
    if playlist_url:
        with st.spinner("Fetching playlist..."):
            videos = get_videos(playlist_url)

        if videos:
            st.session_state.videos = videos
            st.success(f"✅ Playlist loaded with {len(videos)} videos")
        else:
            st.error("❌ Failed to fetch playlist")

# ==============================
# PREVIEW + RANGE
# ==============================
if st.session_state.videos:
    videos = st.session_state.videos
    total_videos = len(videos)

    st.write(f"🎬 Total Videos: {total_videos}")

    st.markdown("### 📋 Preview (First 5 Videos)")
    for i, (_, title) in enumerate(videos[:5], start=1):
        st.write(f"{i}. {title}")

    col1, col2 = st.columns(2)

    with col1:
        start_idx = st.number_input("Start Index", min_value=1, max_value=total_videos, value=1)

    with col2:
        end_idx = st.number_input("End Index", min_value=1, max_value=total_videos, value=min(10, total_videos))

    # ==============================
    # GENERATE
    # ==============================
    if st.button("🚀 Generate Transcript"):
        with st.spinner("Processing... ⏳"):
            batch_results = process_range(videos, start_idx - 1, end_idx)

        st.success("✅ Done!")

        for batch_num, content in batch_results:
            st.download_button(
                label=f"📥 Download Batch {batch_num}",
                data=content,
                file_name=f"transcripts_batch_{batch_num}.txt",
                mime="text/plain"
            )
