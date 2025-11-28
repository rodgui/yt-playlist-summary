# yt-playlist-summary

A Python tool to download YouTube playlists, extract audio, convert to MP3 64kbps mono, transcribe using OpenAI Whisper API, and generate SRT subtitle files.

## Features

- Download videos from YouTube playlists
- Option to download audio only or video + audio
- Extract audio from downloaded videos
- Convert audio to MP3 64kbps mono format (optional)
- Transcribe audio using OpenAI Whisper API
- Generate SRT subtitle files
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
| `--model` | `-m` | Whisper model to use | `whisper-1` |
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

#### Specify Whisper model
```bash
python yt_playlist_summary.py --url "https://youtube.com/playlist?list=PLxxxxxx" --api-key "sk-..." --model whisper-1
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
