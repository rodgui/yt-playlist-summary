#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Checkpoint Manager
       
Manages download progress tracking for playlist processing, enabling
resume capability after interruptions.
"""
       
import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import hashlib
       
logger = logging.getLogger('checkpoint_manager')


class CheckpointManager:
    """Manages checkpoint file for tracking playlist download progress."""
    
    def __init__(self, checkpoint_path: str):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_path: Path to checkpoint JSON file
        """
        self.checkpoint_path = checkpoint_path
        self.data: Dict = {}
        self._load()
    
    def _load(self) -> None:
        """Load existing checkpoint file or initialize empty."""
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(f"📖 Checkpoint carregado: {self.checkpoint_path}")
            except Exception as e:
                logger.warning(f"⚠️  Falha ao carregar checkpoint: {e}")
                self.data = {}
        else:
            self.data = {}
    
    def _save(self) -> None:
        """Persist checkpoint data to disk."""
        try:
            os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
            with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Falha ao salvar checkpoint: {e}")
    
    def initialize_playlist(
        self,
        playlist_url: str,
        video_entries: List[Dict]
    ) -> None:
        """
        Initialize checkpoint for a new playlist or resume existing.
        
        Args:
            playlist_url: YouTube playlist URL
            video_entries: List of video entry dicts from yt-dlp
        """
        playlist_id = self._generate_playlist_id(playlist_url)
        
        # Check if resuming existing checkpoint
        if 'playlist_id' in self.data and self.data['playlist_id'] == playlist_id:
            logger.info("🔄 Retomando playlist existente")
            return
        
        # Initialize new checkpoint
        self.data = {
            'playlist_id': playlist_id,
            'playlist_url': playlist_url,
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'total_videos': len(video_entries),
            'videos': {}
        }
        
        # Register all videos with pending status
        for idx, entry in enumerate(video_entries, 1):
            video_id = entry.get('id', str(idx))
            title = entry.get('title', f'Video {idx}')
            
            self.data['videos'][video_id] = {
                'index': idx,
                'title': title,
                'video_id': video_id,
                'status': 'pending',
                'downloaded_at': None,
                'subtitle_source': None,  # 'youtube' | 'whisper' | None
                'subtitle_files': [],
                'error': None
            }
        
        self._save()
        logger.info(f"📝 Checkpoint inicializado: {len(video_entries)} vídeo(s)")
    
    def is_video_completed(self, video_id: str) -> bool:
        """Check if video was already successfully processed."""
        if 'videos' not in self.data:
            return False
        
        video = self.data['videos'].get(video_id, {})
        return video.get('status') == 'completed'
    
    def mark_video_completed(
        self,
        video_id: str,
        subtitle_source: Optional[str] = None,
        subtitle_files: Optional[List[str]] = None
    ) -> None:
        """
        Mark video as successfully completed.
        
        Args:
            video_id: Video identifier
            subtitle_source: 'youtube', 'whisper', or None
            subtitle_files: List of subtitle file paths
        """
        if 'videos' not in self.data or video_id not in self.data['videos']:
            logger.warning(f"⚠️  Video ID não encontrado no checkpoint: {video_id}")
            return
        
        self.data['videos'][video_id].update({
            'status': 'completed',
            'downloaded_at': datetime.now().isoformat(),
            'subtitle_source': subtitle_source,
            'subtitle_files': subtitle_files or [],
            'error': None
        })
        
        self.data['last_updated'] = datetime.now().isoformat()
        self._save()
        
        # Log progress
        completed = sum(1 for v in self.data['videos'].values() if v['status'] == 'completed')
        total = self.data['total_videos']
        logger.debug(f"✅ Progresso: {completed}/{total} vídeos")
    
    def mark_video_failed(
        self,
        video_id: str,
        error: str
    ) -> None:
        """
        Mark video as failed with error message.
        
        Args:
            video_id: Video identifier
            error: Error description
        """
        if 'videos' not in self.data or video_id not in self.data['videos']:
            logger.warning(f"⚠️  Video ID não encontrado no checkpoint: {video_id}")
            return
        
        self.data['videos'][video_id].update({
            'status': 'failed',
            'error': error[:500],  # Limit error message length
            'downloaded_at': datetime.now().isoformat()
        })
        
        self.data['last_updated'] = datetime.now().isoformat()
        self._save()
    
    def get_pending_videos(self) -> List[Dict]:
        """
        Get list of videos that still need processing.
        
        Returns:
            List of video info dicts (sorted by index)
        """
        if 'videos' not in self.data:
            return []
        
        pending = [
            v for v in self.data['videos'].values()
            if v['status'] in ['pending', 'failed']
        ]
        
        return sorted(pending, key=lambda x: x['index'])
    
    def get_progress_summary(self) -> Dict:
        """
        Get summary of checkpoint progress.
        
        Returns:
            Dict with counts: total, completed, failed, pending
        """
        if 'videos' not in self.data:
            return {
                'total': 0,
                'completed': 0,
                'failed': 0,
                'pending': 0
            }
        
        videos = self.data['videos'].values()
        
        return {
            'total': len(videos),
            'completed': sum(1 for v in videos if v['status'] == 'completed'),
            'failed': sum(1 for v in videos if v['status'] == 'failed'),
            'pending': sum(1 for v in videos if v['status'] == 'pending')
        }
    
    def clear(self) -> None:
        """Clear checkpoint file."""
        if os.path.exists(self.checkpoint_path):
            try:
                os.remove(self.checkpoint_path)
                logger.info(f"🗑️  Checkpoint removido: {self.checkpoint_path}")
            except Exception as e:
                logger.error(f"❌ Falha ao remover checkpoint: {e}")
        
        self.data = {}
    
    @staticmethod
    def _generate_playlist_id(url: str) -> str:
        """Generate deterministic ID from playlist URL."""
        return hashlib.md5(url.encode('utf-8')).hexdigest()[:16]


def get_checkpoint_path(output_dir: str, playlist_url: str) -> str:
    """
    Generate checkpoint file path for a playlist.
    
    Args:
        output_dir: Base output directory
        playlist_url: YouTube playlist URL
        
    Returns:
        Path to checkpoint JSON file
    """
    playlist_id = CheckpointManager._generate_playlist_id(playlist_url)
    return os.path.join(output_dir, f'.checkpoint_{playlist_id}.json')
