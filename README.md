# yt-playlist-summary

A Python tool to download YouTube playlists, extract audio, convert to MP3 64kbps mono, transcribe using OpenAI Whisper API, and generate SRT subtitle files.

## Architecture

The project is organized into two modules with clear separation of concerns:

- **`yt_playlist_summary.py`**: Handles YouTube video downloading, audio extraction, and audio conversion
- **`mywhisper.py`**: Handles audio transcription using OpenAI Whisper API and SRT subtitle generation

This separation allows each module to be used independently or together, making the codebase more maintainable and flexible.

## Features

- Download videos from YouTube playlists
- Option to download audio only or video + audio
- Extract audio from downloaded videos
- Convert audio to MP3 64kbps mono format (optional)
- Transcribe audio using OpenAI Whisper API (via `mywhisper.py`)
- Generate SRT subtitle files with proper timestamp synchronization
- Support for large audio files with automatic chunking
- Transcription caching for improved performance
- Optional translation support
- Comprehensive logging and error handling

## Requirements

- Python 3.10+
- FFmpeg (required by yt-dlp and pydub for audio processing)
- OpenAI API key (for transcription)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/rodgui/yt-playlist-summary.git
cd yt-playlist-summary
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg:
   - **Ubuntu/Debian**: `sudo apt-get install ffmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Usage

### Basic Usage

```bash
python yt_playlist_summary.py --url "PLAYLIST_URL" --api-key "YOUR_OPENAI_API_KEY"
```

### Command Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--url` | `-u` | YouTube playlist or video URL (required) | - |
| `--output` | `-o` | Output directory | `./output` |
| `--api-key` | `-k` | OpenAI API key (or set `OPENAI_API_KEY` env var) | - |
| `--language` | `-l` | Language code for transcription (e.g., en, pt, es) | auto-detect |
| `--audio-only` | `-a` | Download only audio (no video) | `False` |
| `--keep-original` | - | Keep original audio format (no conversion) | `False` |
| `--skip-transcription` | - | Skip transcription step | `False` |
| `--verbose` | `-v` | Enable verbose logging | `False` |

### Examples

#### Download and transcribe a playlist
```bash
python yt_playlist_summary.py --url "https://youtube.com/playlist?list=PLxxxxxx" --api-key "sk-..."
```

#### Download audio only
```bash
python yt_playlist_summary.py --url "https://youtube.com/playlist?list=PLxxxxxx" --api-key "sk-..." --audio-only
```

#### Keep original audio format (no conversion to 64kbps mono)
```bash
python yt_playlist_summary.py --url "https://youtube.com/playlist?list=PLxxxxxx" --api-key "sk-..." --keep-original
```

#### Specify language for transcription
```bash
python yt_playlist_summary.py --url "https://youtube.com/playlist?list=PLxxxxxx" --api-key "sk-..." --language pt
```

#### Skip transcription (download and convert only)
```bash
python yt_playlist_summary.py --url "https://youtube.com/playlist?list=PLxxxxxx" --skip-transcription
```

#### Using environment variable for API key
```bash
export OPENAI_API_KEY="sk-..."
python yt_playlist_summary.py --url "https://youtube.com/playlist?list=PLxxxxxx"
```

### Using mywhisper.py Directly

You can also use `mywhisper.py` directly for standalone audio transcription:

```bash
# Basic transcription
python mywhisper.py --input audio.mp3

# Transcribe with specific language
python mywhisper.py --input audio.mp3 --language pt

# Translate audio to English
python mywhisper.py --input audio.mp3 --translate en

# Translate existing SRT file
python mywhisper.py --only-translation subtitles.srt --translate pt
```

## Output Structure

```
output/
├── downloads/      # Original downloaded files
├── audio/          # Extracted audio files
├── converted/      # Converted audio files (64kbps mono)
└── subtitles/      # Generated SRT subtitle files
```

## Error Handling

The tool includes comprehensive error handling:

- Failed downloads are logged but don't stop processing
- Each video is processed independently
- Summary of successful and failed processing is shown at the end
- Verbose mode (`-v`) provides detailed logging for debugging

## License

MIT License
