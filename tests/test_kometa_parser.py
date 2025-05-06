import os
import pytest
from pathlib import Path
from kometa_ai.kometa.parser import KometaParser
from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.claude.prompts import format_collection_prompt


class TestKometaParser:
    """Tests for the KometaParser class."""
    
    @pytest.fixture
    def test_config_dir(self, tmp_path):
        """Create a temporary directory with test YAML files."""
        # Create test YAML file
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Create a test collection file
        test_file = config_dir / "collections.yml"
        test_file.write_text(
            """collections:
  # === KOMETA-AI ===
  # enabled: true
  # confidence_threshold: 0.7
  # prompt: Identify film noir movies based on these criteria- Made primarily between 1940-1959, Dark, cynical themes and moral ambiguity
  # === END KOMETA-AI ===
  Film Noir:
    radarr_taglist: KAI-film-noir
        
  # === KOMETA-AI ===
  # enabled: false
  # confidence_threshold: 0.6
  # prompt: Identify sci-fi movies
  # === END KOMETA-AI ===
  Sci-Fi:
    radarr_taglist: KAI-sci-fi
"""
        )
        
        # Create a file that should be skipped
        skip_file = config_dir / "_skip.yml"
        skip_file.write_text("# This file should be skipped")
        
        return config_dir
        
    @pytest.fixture
    def test_config_with_tag_mismatch(self, tmp_path):
        """Create a temporary directory with test YAML files containing mismatched tags."""
        config_dir = tmp_path / "config_mismatched"
        config_dir.mkdir()
        
        # Create a test collection file with a mismatched tag
        test_file = config_dir / "collections_mismatched.yml"
        test_file.write_text(
            """collections:
  # === KOMETA-AI ===
  # enabled: true
  # confidence_threshold: 0.7
  # prompt: Identify film noir movies based on these criteria- Made primarily between 1940-1959, Dark, cynical themes and moral ambiguity
  # === END KOMETA-AI ===
  Film Noir:
    radarr_taglist: KAI-wrong-tag
"""
        )
        
        return config_dir
    
    @pytest.fixture
    def test_config_with_bullets(self, tmp_path):
        """Create a temporary directory with test YAML files containing bullet points."""
        config_dir = tmp_path / "config_bullets"
        config_dir.mkdir()
        
        # Create a test collection file with bullet points
        test_file = config_dir / "collections_with_bullets.yml"
        test_file.write_text(
            """collections:
  # === KOMETA-AI ===
  # enabled: true
  # confidence_threshold: 0.7
  # priority: 1
  # prompt: |
  #   Identify film noir movies based on these criteria:
  #   - Made primarily between 1940-1959
  #   - Dark, cynical themes and moral ambiguity
  #   - Visual style emphasizing shadows, unusual angles
  #   - Crime or detective storylines
  #   - Femme fatale character often present
  # === END KOMETA-AI ===
  Film Noir:
    radarr_taglist: KAI-film-noir
"""
        )
        
        return config_dir
    
    def test_find_yaml_files(self, test_config_dir):
        """Test finding YAML files."""
        parser = KometaParser(str(test_config_dir))
        files = parser.find_yaml_files()
        
        assert len(files) == 1
        assert files[0].name == "collections.yml"
    
    def test_extract_ai_blocks(self, test_config_dir):
        """Test extracting AI configuration blocks."""
        parser = KometaParser(str(test_config_dir))
        files = parser.find_yaml_files()
        
        blocks = parser.extract_ai_blocks(files[0])
        
        assert len(blocks) == 2
        assert "Film Noir" in blocks
        assert "Sci-Fi" in blocks
        
        assert blocks["Film Noir"]["enabled"] is True
        assert "Made primarily between 1940-1959" in blocks["Film Noir"]["prompt"]
        assert blocks["Film Noir"]["confidence_threshold"] == 0.7
        
        assert blocks["Sci-Fi"]["enabled"] is False
        assert "Identify sci-fi movies" in blocks["Sci-Fi"]["prompt"]
        assert blocks["Sci-Fi"]["confidence_threshold"] == 0.6
    
    def test_parse_configs(self, test_config_dir):
        """Test parsing all configurations."""
        parser = KometaParser(str(test_config_dir))
        configs = parser.parse_configs()
        
        # Only enabled collections should be returned
        assert len(configs) == 1
        
        config = configs[0]
        assert config.name == "Film Noir"
        assert config.slug == "film-noir"
        assert config.enabled is True
        assert config.confidence_threshold == 0.7
        assert "Made primarily between 1940-1959" in config.prompt
        
        # Test tag generation
        assert config.tag == "KAI-film-noir"
        
    def test_bullet_points_in_prompt(self, test_config_with_bullets):
        """Test handling of multi-line prompts with bullet points."""
        parser = KometaParser(str(test_config_with_bullets))
        configs = parser.parse_configs()
        
        # Verify we have one config
        assert len(configs) == 1
        config = configs[0]
        
        # Check config properties
        assert config.name == "Film Noir"
        assert config.confidence_threshold == 0.7
        assert config.priority == 1
        
        # Check that the prompt contains all bullet points
        prompt_lines = config.prompt.split("\n")
        bullet_lines = [line for line in prompt_lines if line.strip().startswith("-")]
        
        # Verify bullet points are preserved
        assert len(bullet_lines) == 5
        assert any("Made primarily between 1940-1959" in line for line in bullet_lines)
        assert any("Dark, cynical themes and moral ambiguity" in line for line in bullet_lines)
        assert any("Visual style emphasizing shadows, unusual angles" in line for line in bullet_lines)
        assert any("Crime or detective storylines" in line for line in bullet_lines)
        assert any("Femme fatale character often present" in line for line in bullet_lines)
        
        # Verify that configuration options are not part of the prompt
        assert not any("confidence_threshold" in line for line in prompt_lines)
        assert not any("priority" in line for line in prompt_lines)
        
        # Test integration with the prompt formatting function
        formatted_prompt = format_collection_prompt(config)
        
        # Check that the formatted prompt contains all bullet points
        for bullet in bullet_lines:
            assert bullet in formatted_prompt
            
    def test_tag_mismatch_detection(self, test_config_with_tag_mismatch, monkeypatch, caplog):
        """Test detection of mismatched tags."""
        # Ensure auto-fix is disabled
        monkeypatch.setenv('KOMETA_FIX_TAGS', 'false')
        
        parser = KometaParser(str(test_config_with_tag_mismatch))
        files = parser.find_yaml_files()
        
        # Process the file with mismatched tag
        blocks = parser.extract_ai_blocks(files[0])
        
        # Check that warning was logged for the mismatched tag
        assert "Mismatched tag for collection 'Film Noir'" in caplog.text
        assert "Expected: KAI-film-noir, Found: KAI-wrong-tag" in caplog.text
        
        # Verify that auto-fix message was logged
        assert "Set environment variable KOMETA_FIX_TAGS=true to automatically fix mismatched tags" in caplog.text
        
    def test_tag_mismatch_correction(self, test_config_with_tag_mismatch, monkeypatch):
        """Test correction of mismatched tags."""
        # Enable auto-fix
        monkeypatch.setenv('KOMETA_FIX_TAGS', 'true')
        
        parser = KometaParser(str(test_config_with_tag_mismatch))
        files = parser.find_yaml_files()
        
        # Process the file with mismatched tag, which should trigger auto-fix
        blocks = parser.extract_ai_blocks(files[0])
        
        # Read the file content to check if tag was fixed
        file_path = files[0]
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check that tag was fixed
        assert "radarr_taglist: KAI-film-noir" in content
        assert "radarr_taglist: KAI-wrong-tag" not in content