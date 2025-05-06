import os
import pytest
from pathlib import Path
from kometa_ai.kometa.parser import KometaParser
from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.utils.helpers import slugify


class TestTagMismatch:
    """Tests for tag mismatch detection and correction functionality."""
    
    @pytest.fixture
    def test_config_with_mismatched_tag(self, tmp_path):
        """Create a temporary directory with test YAML files containing mismatched tags."""
        config_dir = tmp_path / "config_mismatched"
        config_dir.mkdir()
        
        # Create a test collection file with mismatched tag
        test_file = config_dir / "collections_mismatched.yml"
        test_file.write_text(
            """collections:
  # === KOMETA-AI ===
  # enabled: true
  # confidence_threshold: 0.7
  # prompt: Identify film noir movies based on these criteria- Made primarily between 1940-1959, Dark, cynical themes and moral ambiguity
  # === END KOMETA-AI ===
  Film Noir:
    radarr_taglist: KAI-film-noire
        
  # === KOMETA-AI ===
  # enabled: true
  # confidence_threshold: 0.6
  # prompt: Identify sci-fi movies
  # === END KOMETA-AI ===
  Sci-Fi:
    radarr_taglist: KAI-science-fiction
"""
        )
        
        return config_dir
    
    def test_tag_mismatch_detection(self, test_config_with_mismatched_tag, monkeypatch, caplog):
        """Test detection of mismatched tags."""
        # Ensure auto-fix is disabled
        monkeypatch.setenv('KOMETA_FIX_TAGS', 'false')
        
        parser = KometaParser(str(test_config_with_mismatched_tag))
        files = parser.find_yaml_files()
        
        # Process the file with mismatched tags
        blocks = parser.extract_ai_blocks(files[0])
        
        # Check that warnings were logged for both mismatched tags
        assert "Mismatched tag for collection 'Film Noir'" in caplog.text
        assert "Expected: KAI-film-noir, Found: KAI-film-noire" in caplog.text
        
        assert "Mismatched tag for collection 'Sci-Fi'" in caplog.text
        assert "Expected: KAI-sci-fi, Found: KAI-science-fiction" in caplog.text
        
        # Verify that auto-fix message was logged
        assert "Set environment variable KOMETA_FIX_TAGS=true to automatically fix mismatched tags" in caplog.text
    
    def test_tag_mismatch_correction(self, test_config_with_mismatched_tag, monkeypatch):
        """Test correction of mismatched tags."""
        # Enable auto-fix
        monkeypatch.setenv('KOMETA_FIX_TAGS', 'true')
        
        parser = KometaParser(str(test_config_with_mismatched_tag))
        files = parser.find_yaml_files()
        
        # Process the file with mismatched tags, which should trigger auto-fix
        blocks = parser.extract_ai_blocks(files[0])
        
        # Read the file content to check if tags were fixed
        file_path = files[0]
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check that tags were fixed
        assert "radarr_taglist: KAI-film-noir" in content
        assert "radarr_taglist: KAI-sci-fi" in content
        
        # Verify the original incorrect tags are no longer present
        assert "radarr_taglist: KAI-film-noire" not in content
        assert "radarr_taglist: KAI-science-fiction" not in content
    
    def test_check_radarr_taglist(self, test_config_with_mismatched_tag):
        """Test the check_radarr_taglist method."""
        parser = KometaParser(str(test_config_with_mismatched_tag))
        files = parser.find_yaml_files()
        
        # Check Film Noir tag
        is_valid, current_tag = parser.check_radarr_taglist(files[0], "Film Noir")
        assert is_valid is False
        assert current_tag == "KAI-film-noire"
        
        # Check Sci-Fi tag
        is_valid, current_tag = parser.check_radarr_taglist(files[0], "Sci-Fi")
        assert is_valid is False
        assert current_tag == "KAI-science-fiction"
        
        # Check expected tag generation
        expected_tag = parser.get_expected_tag("Film Noir")
        assert expected_tag == "KAI-film-noir"
    
    def test_fix_radarr_taglist(self, test_config_with_mismatched_tag):
        """Test the fix_radarr_taglist method."""
        parser = KometaParser(str(test_config_with_mismatched_tag))
        files = parser.find_yaml_files()
        
        # Fix Film Noir tag
        result = parser.fix_radarr_taglist(files[0], "Film Noir", "KAI-film-noire")
        assert result is True
        
        # Verify the tag was fixed
        with open(files[0], 'r') as f:
            content = f.read()
        
        assert "radarr_taglist: KAI-film-noir" in content
        assert "radarr_taglist: KAI-film-noire" not in content
        
        # Sci-Fi tag should still be incorrect as we only fixed Film Noir
        assert "radarr_taglist: KAI-science-fiction" in content