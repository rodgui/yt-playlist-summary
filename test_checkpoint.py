#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for checkpoint functionality
"""

import os
import tempfile
from checkpoint_manager import CheckpointManager, get_checkpoint_path

def test_checkpoint_basic():
    """Test basic checkpoint operations."""
    print("Testing basic checkpoint operations...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, 'test_checkpoint.json')
        manager = CheckpointManager(checkpoint_path)
        
        # Simulate playlist
        playlist_url = "https://www.youtube.com/playlist?list=TEST123"
        video_entries = [
            {'id': 'vid1', 'title': 'Video 1'},
            {'id': 'vid2', 'title': 'Video 2'},
            {'id': 'vid3', 'title': 'Video 3'},
        ]
        
        # Initialize
        manager.initialize_playlist(playlist_url, video_entries)
        print(f"✓ Initialized with {len(video_entries)} videos")
        
        # Check progress
        progress = manager.get_progress_summary()
        assert progress['total'] == 3
        assert progress['pending'] == 3
        assert progress['completed'] == 0
        print(f"✓ Progress: {progress}")
        
        # Mark one completed
        manager.mark_video_completed('vid1', 'youtube', ['vid1.pt.srt'])
        assert manager.is_video_completed('vid1')
        assert not manager.is_video_completed('vid2')
        print("✓ Marked vid1 as completed")
        
        # Mark one failed
        manager.mark_video_failed('vid2', 'Test error')
        progress = manager.get_progress_summary()
        assert progress['completed'] == 1
        assert progress['failed'] == 1
        assert progress['pending'] == 1
        print(f"✓ Progress after operations: {progress}")
        
        # Test pending videos
        pending = manager.get_pending_videos()
        assert len(pending) == 2  # vid2 (failed) and vid3 (pending)
        print(f"✓ Pending videos: {[v['video_id'] for v in pending]}")
        
        print("\n✅ All tests passed!")

def test_checkpoint_persistence():
    """Test checkpoint persistence across instances."""
    print("\nTesting checkpoint persistence...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, 'test_checkpoint.json')
        
        # First instance
        manager1 = CheckpointManager(checkpoint_path)
        playlist_url = "https://www.youtube.com/playlist?list=TEST456"
        video_entries = [
            {'id': 'v1', 'title': 'Video 1'},
            {'id': 'v2', 'title': 'Video 2'},
        ]
        manager1.initialize_playlist(playlist_url, video_entries)
        manager1.mark_video_completed('v1', 'whisper', ['v1.srt'])
        print("✓ First instance created and marked v1 completed")
        
        # Second instance (simulating restart)
        manager2 = CheckpointManager(checkpoint_path)
        assert manager2.is_video_completed('v1')
        assert not manager2.is_video_completed('v2')
        progress = manager2.get_progress_summary()
        assert progress['completed'] == 1
        assert progress['pending'] == 1
        print("✓ Second instance loaded checkpoint correctly")
        
        print("\n✅ Persistence test passed!")

def test_playlist_id_generation():
    """Test deterministic playlist ID generation."""
    print("\nTesting playlist ID generation...")
    
    url1 = "https://www.youtube.com/playlist?list=ABC123"
    url2 = "https://www.youtube.com/playlist?list=ABC123"
    url3 = "https://www.youtube.com/playlist?list=XYZ789"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        path1 = get_checkpoint_path(tmpdir, url1)
        path2 = get_checkpoint_path(tmpdir, url2)
        path3 = get_checkpoint_path(tmpdir, url3)
        
        assert path1 == path2, "Same URL should generate same path"
        assert path1 != path3, "Different URLs should generate different paths"
        print(f"✓ URL1 path: {os.path.basename(path1)}")
        print(f"✓ URL3 path: {os.path.basename(path3)}")
        
        print("\n✅ ID generation test passed!")

if __name__ == '__main__':
    test_checkpoint_basic()
    test_checkpoint_persistence()
    test_playlist_id_generation()
    print("\n" + "=" * 60)
    print("🎉 ALL CHECKPOINT TESTS PASSED!")
    print("=" * 60)
