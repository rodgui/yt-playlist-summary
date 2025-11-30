# 🎬 YouTube Playlist Summary

Transform YouTube playlists into structured study material.

An automated tool that downloads videos, extracts subtitles (native or AI), and generates consolidated educational content — all in a single command.

---

## 🎯 Purpose

Watching hours of educational videos is time-consuming. This project solves it by:

1. Downloading videos or audio from YouTube playlists
2. Obtaining subtitles automatically (prefers native; uses Whisper AI as fallback)
3. Generating consolidated study material via GPT — executive summary, key concepts, per-video content, examples, exercises, and a glossary

Result: A complete Markdown document that significantly reduces the need to watch videos.

---

## 📖 The Generated Study Material

"Turn 10 hours of video into 30 minutes of focused reading."

The output is a complete educational document structured by AI to maximize learning:

Structure:
- Executive Summary
- Key Concepts with definitions and examples
- Per-Video Content (summary, best practices, detailed analysis)
- Practical Examples (code, diagrams, APIs)
- Exercises and Action Items
- Technical Glossary
- References and Resources
- Appendices (templates, comparative tables, described flowcharts)

Benefits:
- Save time: absorb hours of content in minutes
- Easy review: searchable document
- Language flexibility: generate material in your preferred language
- Offline-ready: print/export to PDF
- Active learning: includes exercises and examples

---

## ✨ Key Features

- Smart download with rate-limit control
- Automatic subtitles: prefers YouTube; Whisper AI fallback
- Checkpoint/resume: safe to interrupt and continue
- Full study material via GPT
- Smart multi-language: detects OS language, prioritizes subtitles, avoids duplicates
- Audio-only mode to save disk space

---

## 📋 Requirements

- Python 3.10+
- FFmpeg and ffprobe installed and on PATH
- OpenAI API key (for Whisper transcription and GPT content)

FFmpeg install:
- Windows (winget): `winget install FFmpeg.FFmpeg`
- Windows (Chocolatey): `choco install ffmpeg`
- macOS: `brew install ffmpeg`
- Linux (Debian/Ubuntu): `sudo apt install ffmpeg`

---

## 🚀 Installation

1. Clone:
```bash
git clone https://github.com/your-user/yt-playlist-summary.git
cd yt-playlist-summary
```

2. Virtual env:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/macOS
```

3. Install deps:
```bash
pip install -r requirements.txt
```

4. Set API key:
```bash
# Environment variable
export OPENAI_API_KEY="sk-..."   # Linux/macOS
set OPENAI_API_KEY=sk-...        # Windows CMD
$env:OPENAI_API_KEY="sk-..."     # Windows PowerShell

# Or .env file
echo OPENAI_API_KEY=sk-... > .env
```

---

## 📖 Usage

Basic:
```bash
python yt_playlist_summary.py --url "PLAYLIST_URL"
```

Default behavior:
- Downloads all videos
- Searches native subtitles (pt-BR, en)
- Falls back to Whisper if none found
- Generates consolidated study material
- Checkpoint enabled (resume supported)

Examples:
```bash
# Full processing
python yt_playlist_summary.py --url "https://youtube.com/playlist?list=..."

# Interactive mode
python yt_playlist_summary.py --url "URL" --interactive

# Audio-only
python yt_playlist_summary.py --url "URL" --audio-only

# Force Whisper (ignore native subs)
python yt_playlist_summary.py --url "URL" --no-prefer-existing-subtitles

# No study material (download + subs only)
python yt_playlist_summary.py --url "URL" --no-study-material

# Clear checkpoint
python yt_playlist_summary.py --url "URL" --clear-checkpoint

# Subtitle source priority (BCP 47)
python yt_playlist_summary.py --url "URL" --source-language en,pt-BR

# Study material in English from Portuguese subtitles
python yt_playlist_summary.py --url "URL" --source-language pt-BR --study-language en

# English material using English subtitles
python yt_playlist_summary.py --url "URL" --source-language en --study-language en

# Portuguese material using English subs (translate content)
python yt_playlist_summary.py --url "URL" --source-language en --study-language pt

# Force specific languages (override OS detection)
python yt_playlist_summary.py --url "URL" --source-language ja,en --study-language ja
```

Output structure:
```
output/
├── downloads/          # Original videos/audio
├── audio/              # Extracted audio (if not audio-only)
├── converted/          # 64kbps mono audio (for Whisper)
├── subtitles/          # .srt files
├── study_material_*.md # Generated study material
└── .checkpoint_*.json  # Progress tracking (resume)
```

---

## ⚙️ CLI Parameters

- `-u, --url` (required): playlist or video URL
- `-k, --api-key`: OpenAI key (or env OPENAI_API_KEY)
- `-o, --output`: output directory (default `./output`)
- `-l, --language`: Whisper transcription language (auto)
- `-a, --audio-only`: download audio only
- `-i, --interactive`: interactive confirmations
- `-v, --verbose`: detailed logs
- `--subtitle-languages`: native subs search (default `pt-BR,en`)
- `--download-delay`: seconds between downloads (default 5)
- `--keep-original`: keep original audio (skip conversion)
- `--skip-transcription`: skip subtitle generation
- `--no-prefer-existing-subtitles`: force Whisper
- `--no-study-material`: disable study material generation
- `--source-language`: subtitle source priority (e.g., `pt-BR,en`)
- `--study-language`: output material language (BCP 47)
- `--no-checkpoint`: disable checkpoint/resume
- `--clear-checkpoint`: clear checkpoint and restart

---

## 🔄 Checkpoint System

Progress is saved automatically. If interrupted (Ctrl+C), simply re-run:

```bash
# First run stopped at 5/20
python yt_playlist_summary.py --url "URL"
# ^C

# Second run resumes at 6/20
python yt_playlist_summary.py --url "URL"
```

---

## 🛠️ Helper Scripts

Translate existing subtitles:
```bash
python translate_sub.py --input ./output/subtitles/video.pt-BR.srt --source pt-BR --target en
```

Generate study material from ready subtitles:
```bash
# OS-based defaults
python generate_study_material.py -s ./output/subtitles

# Specify source priority and output language
python generate_study_material.py --subtitle-dir ./output/subtitles --source-language pt-BR,en --output-language pt

# Interactive
python generate_study_material.py -s ./output/subtitles -i

# Consolidate only (no GPT)
python generate_study_material.py -s ./output/subtitles --skip-gpt
```

Transcribe standalone audio:
```bash
python mywhisper.py --input audio.mp3
```

Rename files using checkpoint:
```bash
python rename_from_checkpoint.py --checkpoint output/.checkpoint_abc123.json
```

---

## 💰 Cost Estimates (OpenAI)

- Whisper (transcription): ~$0.006 per audio minute
- GPT (study material): ~$0.02–0.05 per typical playlist (5–10 videos)

Tip: keep `--prefer-existing-subtitles` enabled (default) to save — native subs are free!

---

## 🏗️ Project Architecture

```
yt-playlist-summary/
├── yt_playlist_summary.py     # Main pipeline orchestrator
├── mywhisper.py               # Whisper transcription + cache + SRT
├── generate_study_material.py # Study material generator
├── language_utils.py          # OS language detection and smart selection
├── checkpoint_manager.py      # Checkpoint/resume
├── translate_sub.py           # SRT translation via GPT
├── rename_from_checkpoint.py  # Rename utility
├── requirements.txt           # Dependencies
└── README.md / README_en.md
```

---

## 🌐 Smart Language Selection

The system detects your OS language and sets defaults:

- OS in Portuguese:
  - Source: `pt-BR, pt, und`
  - Output: `pt`
- OS in English:
  - Source: `en-US, en, und`
  - Output: `en`

How it works:
1. Groups subtitles by video (index based on filename)
2. Selects one subtitle per video according to priority
3. Avoids duplicates to save GPT tokens

Supported language codes (BCP 47):
`pt`, `pt-BR`, `en`, `en-US`, `es`, `fr`, `de`, `it`, `ja`, `zh`, `ko`, `ru`, `ar`, `hi`

---

## ❓ Troubleshooting

- FFmpeg not found → install FFmpeg and add to PATH
- API key missing → set `OPENAI_API_KEY` or `--api-key`
- Rate-limiting errors → increase `--download-delay` (e.g., 10 or 15)
- Private/unavailable video → skipped automatically
- Corrupted checkpoint → use `--clear-checkpoint`

---

## 📄 License

MIT License — see LICENSE.

---

## 🤝 Contributing

Contributions welcome! Please keep responsibilities separated:
- `yt_playlist_summary.py` → download and audio pre-processing
- `mywhisper.py` → transcription and subtitle handling
- New modules → independent features

Made to make learning more efficient.