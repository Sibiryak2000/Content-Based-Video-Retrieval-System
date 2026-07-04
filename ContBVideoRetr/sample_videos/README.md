# Sample videos

Short MP4 clips used by the GUI shell for local playback tests.

Generate them with:

```bash
cd ContRetr
python scripts/generate_sample_videos.py
```

This creates six ~3 second clips (H.264-compatible `mp4v` in an MP4 container).
Replace these with ffmpeg-transcoded proxies from the V3C-1 dataset when the
data pipeline is ready.
