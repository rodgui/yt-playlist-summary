# 🎬 YouTube Playlist Summary

**Transform YouTube playlists into structured study material.**

An automated tool that downloads videos, extracts subtitles (native or AI-powered), and generates consolidated educational material — all in a single command.

---

## 🎯 Purpose

Watching hours of educational videos is time-consuming. This project solves this problem by:

1. **Downloading** videos or audio from YouTube playlists
2. **Obtaining subtitles** automatically (prioritizes native subtitles; uses Whisper AI as fallback)
3. **Generating study material** consolidated via GPT — summaries, key concepts, practical examples, and glossary

**Result:** A complete Markdown document that replaces the need to watch the videos.

**‼️ Note: ‼️** <u>The cost of using OpenAI API (Whisper and Consolidation) is based on token consumption and varies according to playlist size and video duration. Test with small playlists to evaluate costs before using on larger lists!</u>

---

## 📖 The Generated Study Material

> **"Transform 10 hours of video into 30 minutes of focused reading."**

The generated material is not a simple summary — it's a **complete educational document** structured by AI to maximize your learning:

### 📋 Document Structure

```
📚 Study Material - [Playlist Name]
├── 📌 Executive Summary
│   └── Overview of all content in a few paragraphs
├── 🔑 Key Concepts
│   └── Definitions, context, relationships, and examples for each concept
├── 🎬 Content by Video
|   |── Individual summary of each video
|   |── Tips and best practices
│   └── Detailed analysis preserving the original sequence
├── 💡 Examples and Practical Cases
│   └── Code, diagrams, data models, APIs
├── ✏️ Exercises and Action Points
|   |── Suggested projects for applying concepts
│   └── Practical activities for reinforcement
├── 📖 Technical Glossary
│   └── Important terms with clear definitions
├── 📚 References and Resources
│   └── Links for deeper learning
└── 📎 Appendices
    └── Templates, snippets, comparison tables, described flowcharts
```

### 🎯 Benefits

| Problem                      | Solution                                                         |
| ---------------------------- | ---------------------------------------------------------------- |
| ⏰ **Lack of time**          | Absorb hours of video content in minutes                         |
| 🔄 **Difficult review**      | Searchable document — find any concept instantly                 |
| 📝 **Scattered notes**       | Everything consolidated in a single Markdown file                |
| 🌍 **Language**              | Generate material in your language, even from foreign videos     |
| 💾 **Offline**               | Study without internet, print, export to PDF                     |
| 🎓 **Active learning**       | Exercises and practical examples included                        |

### 💼 Use Cases

- **Students:** Exam preparation from recorded classes
- **Professionals:** Quick training on new technologies
- **Companies:** Internal training documentation
- **Content creators:** Foundation for articles, posts, and derivative courses
- **Researchers:** Systematic analysis of video content

### 📊 Real Example

From a playlist with **2 videos** (https://www.youtube.com/watch?v=HA414QD3qFw / https://www.youtube.com/watch?v=rNu1gUDnkuY) (~2 min each), the system generated:

- **738 lines** of structured content
- **13 key concepts** with complete definitions
- **1 detailed case study** (ClickTravel) with architecture and APIs
- **Practical exercises** and action checklist
- **Glossary** with 20+ technical terms

**Cost:** ~$0.03 (GPT) | **Time:** ~2 minutes | **Value:** Priceless ✨

---

## ✨ Main Features

| Feature                        | Description                                                       |
| ------------------------------ | ----------------------------------------------------------------- |
| 📥 **Intelligent download**    | Downloads videos/audio with rate-limiting control                 |
| 📝 **Automatic subtitles**     | Prioritizes YouTube subtitles; uses Whisper AI if unavailable     |
| 🔄 **Checkpoint/Resume**       | Interrupt and resume at any time (safe Ctrl+C)                    |
| 📚 **Study material**          | Generates complete educational document via GPT                   |
| 🌍 **Intelligent multi-language** | Detects OS language, selects subtitles by priority, avoids duplicates |
| 🎵 **Audio mode**              | Option to download audio only (space savings)                     |

---

## 📋 Prerequisites

- **Python** 3.10 or higher
- **FFmpeg** and **ffprobe** installed and in PATH
- **OpenAI API Key** (for Whisper transcription and material generation)
  - Get it at: https://platform.openai.com/account/api-keys (step-by-step guide below)

### How to get OpenAI API key
1. Access [OpenAI Platform](https://platform.openai.com/).
2. Log in or create an account.
3. In the dashboard, go to "API Keys" in the side menu.
4. Click "Create new secret key".
5. Copy the generated key (starts with "sk-...") and save it in a secure location.
6. Use this key to configure the `OPENAI_API_KEY` environment variable or pass via `--api-key` parameter.

### Configure the `OPENAI_API_KEY` environment variable
- **Linux/macOS:**
  ```bash
  export OPENAI_API_KEY="sk-..."
  ```
- **Windows CMD:**
  ```cmd
  set OPENAI_API_KEY=sk-...
  ```
- **Windows PowerShell:** 
  ```powershell
  $env:OPENAI_API_KEY="sk-..."
  ```   
  
### FFmpeg Installation

**Windows (via winget):**
```bash
winget install FFmpeg.FFmpeg
```

**Windows (via Chocolatey):**
```bash
choco install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install ffmpeg
```

---

## 🚀 Installation

1. **Clone the repository:**
```bash
git clone https://github.com/your-username/yt-playlist-summary.git
cd yt-playlist-summary
```

2. **Create a virtual environment (recommended):**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/macOS
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure the API key:**
```bash
# Option 1: Environment variable
export OPENAI_API_KEY="sk-..."  # Linux/macOS
set OPENAI_API_KEY=sk-...       # Windows CMD
$env:OPENAI_API_KEY="sk-..."    # Windows PowerShell

# Option 2: .env file at project root
echo OPENAI_API_KEY=sk-... > .env
```

---

## 📖 Usage

### Basic Command

```bash
python yt_playlist_summary.py --url "PLAYLIST_URL"
```

**What happens by default:**
1. ✅ Downloads all videos in the playlist
2. ✅ Searches for native subtitles (pt-BR, en)
3. ✅ If no subtitles found → transcribes via Whisper AI
4. ✅ Generates consolidated study material
5. ✅ Checkpoint enabled (can interrupt and resume)

### Practical Examples

```bash
# Process complete playlist (default behavior)
python yt_playlist_summary.py --url "https://youtube.com/playlist?list=..."

# Interactive mode (confirms before each step)
python yt_playlist_summary.py --url "URL" --interactive

# Audio only (space savings)
python yt_playlist_summary.py --url "URL" --audio-only

# Force Whisper usage (ignore native subtitles)
python yt_playlist_summary.py --url "URL" --no-prefer-existing-subtitles

# No study material (download + subtitles only)
python yt_playlist_summary.py --url "URL" --no-study-material

# Clear checkpoint and reprocess everything
python yt_playlist_summary.py --url "URL" --clear-checkpoint

# Specify source language for subtitles (priority)
python yt_playlist_summary.py --url "URL" --source-language pt-BR,en

# Study material in English from Portuguese subtitles
python yt_playlist_summary.py --url "URL" --source-language pt-BR --study-language en

# Material in English using English subtitles
python yt_playlist_summary.py --url "URL" --source-language en --study-language en

# Material in Portuguese using English subtitles (automatic translation)
python yt_playlist_summary.py --url "URL" --source-language en --study-language pt

# Force specific language (ignore OS detection)
python yt_playlist_summary.py --url "URL" --source-language ja,en --study-language ja
```

### Output Structure

```
output/
├── downloads/          # Original videos/audio
├── audio/              # Extracted audio (when needed)
├── converted/          # 64kbps mono audio (for Whisper)
├── subtitles/          # .srt files
├── study_material_*.md # Generated study material
└── .checkpoint_*.json  # Progress (for resume)
```

---

## ⚙️ Available Parameters

| Parameter                        | Default              | Description                                   |
| -------------------------------- | -------------------- | --------------------------------------------- |
| `-u, --url`                      | *required*           | Playlist or video URL                         |
| `-k, --api-key`                  | env `OPENAI_API_KEY` | OpenAI API key                                |
| `-o, --output`                   | `./output`           | Output directory                              |
| `-l, --language`                 | auto-detect          | Language for Whisper transcription            |
| `-a, --audio-only`               | `False`              | Download audio only                           |
| `-i, --interactive`              | `False`              | Interactive mode with confirmations           |
| `-v, --verbose`                  | `False`              | Detailed logs                                 |
| `--subtitle-languages`           | `pt-BR,en`           | Languages to search for subtitles             |
| `--download-delay`               | `5`                  | Seconds between downloads                     |
| `--keep-original`                | `False`              | Keep audio without conversion                 |
| `--skip-transcription`           | `False`              | Skip subtitle step                            |
| `--no-prefer-existing-subtitles` | `False`              | Force Whisper (ignore native subtitles)       |
| `--no-study-material`            | `False`              | Do not generate study material                |
| `--source-language`              | *OS language*        | Source subtitle language(s) (e.g., `pt-BR,en`) |
| `--study-language`               | *OS language*        | Output material language                      |
| `--no-checkpoint`                | `False`              | Disable checkpoint                            |
| `--clear-checkpoint`             | `False`              | Clear checkpoint and restart                  |

---

## 🔄 Checkpoint System

The project saves progress automatically. If interrupted (Ctrl+C), just run the same command again:

```bash
# First run - interrupted at video 5/20
python yt_playlist_summary.py --url "URL"
# ^C

# Second run - resumes from video 6
python yt_playlist_summary.py --url "URL"
# 🔄 RESUMING DOWNLOAD
# ✅ Already completed: 5/20
```

---

## 🛠️ Auxiliary Scripts

### Translate existing subtitles

```bash
python translate_sub.py \
  --input ./output/subtitles/video.pt-BR.srt \
  --source pt-BR \
  --target en
```

### Generate study material from existing subtitles

```bash
# Use system defaults (detects OS language)
python generate_study_material.py -s ./output/subtitles

# Specify source and output language
python generate_study_material.py \
  --subtitle-dir ./output/subtitles \
  --source-language pt-BR,en \
  --output-language pt

# Interactive mode (asks for languages)
python generate_study_material.py -s ./output/subtitles -i

# Consolidate only (without GPT)
python generate_study_material.py -s ./output/subtitles --skip-gpt
```

### Transcribe isolated audio file

```bash
python mywhisper.py --input audio.mp3
```

### Rename files using checkpoint

```bash
python rename_from_checkpoint.py \
  --checkpoint output/.checkpoint_abc123.json
```

---

## 💰 Cost Estimates (OpenAI)

| Operation                | Approximate Cost                           |
| ------------------------ | ------------------------------------------ |
| Whisper (transcription)  | ~$0.006 per minute of audio                |
| GPT (study material)     | ~$0.02-0.05 per typical playlist (5-10 videos) |

**Tip:** Use `--prefer-existing-subtitles` (default) to save money — native subtitles are free!

---

## 🏗️ Project Architecture

```
yt-playlist-summary/
├── yt_playlist_summary.py    # Main pipeline orchestrator
├── mywhisper.py              # Whisper transcription + cache
├── generate_study_material.py # Educational material generation
├── language_utils.py         # OS language detection and intelligent selection
├── checkpoint_manager.py      # Checkpoint/resume system
├── translate_sub.py          # SRT translation via GPT
├── rename_from_checkpoint.py # Renaming utility
├── requirements.txt          # Python dependencies
└── README.md
```

---

## 🌐 Intelligent Language Selection

The system automatically detects your operating system language and configures defaults:

| Portuguese OS           | English OS              |
| ----------------------- | ----------------------- |
| Source: `pt-BR, pt, und` | Source: `en-US, en, und` |
| Output: `pt`             | Output: `en`             |

### How it works

1. **Groups subtitles by video** — identifies index by filename
2. **Selects one subtitle per video** — uses configured language priority
3. **Avoids duplicates** — saves GPT tokens!

**Practical example:**
```
Subtitles/
├── 1. Intro.en.srt
├── 1. Intro.pt-BR.srt   ← selected (pt-BR has priority)
├── 2. Review.en.srt
└── 2. Review.pt-BR.srt  ← selected

Result: 2 subtitles processed instead of 4!
```

### Supported language codes (BCP 47)

`pt`, `pt-BR`, `en`, `en-US`, `es`, `fr`, `de`, `it`, `ja`, `zh`, `ko`, `ru`, `ar`, `hi`

---

## ❓ Troubleshooting

| Problem                    | Solution                                      |
| -------------------------- | --------------------------------------------- |
| `FFmpeg not found`         | Install FFmpeg and add to PATH                |
| `API key not found`        | Configure `OPENAI_API_KEY` via env or `--api-key` |
| Rate-limiting error        | Increase `--download-delay` (e.g., 10 or 15)  |
| Private/unavailable video  | Script automatically skips and continues      |
| Corrupted checkpoint       | Use `--clear-checkpoint` to restart           |

---

## ☕ Buy me a coffee?

If this project has already saved you hours of YouTube videos, imagine what it does with a coffee.
Support a developer who trades sleep for lines of code — and help this project continue preventing you from watching 3-hour lectures at 12 different speeds.

If you enjoyed it, consider buying me a coffee. I promise to spend it on caffeine… and maybe more features.

<center><a href="https://www.buymeacoffee.com/rodgui" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a></center>

---

## 🤝 Contributions

Contributions are welcome! Please maintain separation of responsibilities:
- `yt_playlist_summary.py` → download and preprocessing
- `mywhisper.py` → transcription and subtitle manipulation
- New modules → independent features

---

**Made with ❤️ to make learning more efficient.**
