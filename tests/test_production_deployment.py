import os
import subprocess
import time
import unittest
import requests
import json
import pytest
from pathlib import Path

# Skip these tests on CI or when explicitly requested to skip
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_PRODUCTION_TESTS") == "true" or os.environ.get("CI") == "true",
    reason="Production deployment tests are skipped on CI or when explicitly requested"
)

class TestProductionDeployment(unittest.TestCase):
    """Integration tests for production deployment."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment."""
        # Create test directories
        cls.test_root = Path("/tmp/kometa_ai_test")
        cls.kometa_config_dir = cls.test_root / "kometa-config"
        cls.state_dir = cls.test_root / "state"
        cls.logs_dir = cls.test_root / "logs"
        
        # Create test directories
        cls.test_root.mkdir(exist_ok=True)
        cls.kometa_config_dir.mkdir(exist_ok=True)
        cls.state_dir.mkdir(exist_ok=True)
        cls.logs_dir.mkdir(exist_ok=True)
        
        # Copy test configuration
        subprocess.run(["cp", "-r", "config-examples/basic-collections.yml", 
                      str(cls.kometa_config_dir / "collections.yml")])
        
        # Create docker-compose.test.yml
        cls._create_test_docker_compose()
        
        # Start test containers
        subprocess.run(["docker-compose", "-f", "docker-compose.test.yml", "up", "-d"])
        
        # Wait for containers to start
        time.sleep(5)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after tests."""
        # Stop docker containers
        subprocess.run(["docker-compose", "-f", "docker-compose.test.yml", "down"])
        
        # Clean up test directories
        subprocess.run(["rm", "-rf", str(cls.test_root)])
    
    @classmethod
    def _create_test_docker_compose(cls):
        """Create a test docker-compose file."""
        compose_content = """
version: '3'
services:
  kometa-ai:
    build: 
      context: .
      dockerfile: Dockerfile
    container_name: kometa-ai-test
    volumes:
      - {kometa_config}:/app/kometa-config
      - {state}:/app/state
      - {logs}:/app/logs
    environment:
      - RADARR_URL=http://mock-radarr:1080
      - RADARR_API_KEY=test_api_key
      - CLAUDE_API_KEY=test_api_key
      - DEBUG_LOGGING=true
    healthcheck:
      test: ["CMD", "python", "-m", "kometa_ai", "--health-check"]
      interval: 10s
      timeout: 5s
      retries: 3
    command: ["--health-check"]
  
  mock-radarr:
    image: mockserver/mockserver
    container_name: mock-radarr-test
    ports:
      - "7878:1080"
    volumes:
      - ./test_data/mock_radarr:/mockserver/mockserver_expectations
""".format(
    kometa_config=cls.kometa_config_dir,
    state=cls.state_dir,
    logs=cls.logs_dir
)
        with open("docker-compose.test.yml", "w") as f:
            f.write(compose_content)
    
    def test_container_health(self):
        """Test that the Docker container's health check passes."""
        # Check if the container is running and healthy
        result = subprocess.run(
            ["docker", "inspect", "--format='{{.State.Health.Status}}'", "kometa-ai-test"],
            capture_output=True,
            text=True
        )
        # Wait for healthcheck to run (might be starting)
        time.sleep(10)
        
        # Check again if needed
        if "starting" in result.stdout:
            time.sleep(10)
            result = subprocess.run(
                ["docker", "inspect", "--format='{{.State.Health.Status}}'", "kometa-ai-test"],
                capture_output=True,
                text=True
            )
        
        self.assertIn("healthy", result.stdout)
    
    def test_docker_image_structure(self):
        """Test that the Docker image has the correct structure."""
        # Inspect image layers
        result = subprocess.run(
            ["docker", "history", "kometa-ai-test"],
            capture_output=True,
            text=True
        )
        
        # Check for multi-stage build evidence
        self.assertIn("FROM python", result.stdout)
        
        # Check for proper permissions
        permission_check = subprocess.run(
            ["docker", "exec", "kometa-ai-test", "ls", "-la", "/app"],
            capture_output=True,
            text=True
        )
        # Look for non-root user ownership
        self.assertIn("kometa", permission_check.stdout)
    
    def test_environment_variables(self):
        """Test that environment variables are correctly processed."""
        # Execute a command to print environment variables
        result = subprocess.run(
            ["docker", "exec", "kometa-ai-test", "python", "-c", 
            "import os; print(os.environ.get('DEBUG_LOGGING'))"],
            capture_output=True,
            text=True
        )
        
        # Verify the value matches what we set
        self.assertIn("True", result.stdout)
    
    def test_volume_mounts(self):
        """Test that volumes are correctly mounted."""
        # Check kometa-config volume
        result = subprocess.run(
            ["docker", "exec", "kometa-ai-test", "ls", "/app/kometa-config"],
            capture_output=True,
            text=True
        )
        self.assertIn("collections.yml", result.stdout)
        
        # Verify the content matches our test file
        result = subprocess.run(
            ["docker", "exec", "kometa-ai-test", "cat", "/app/kometa-config/collections.yml"],
            capture_output=True,
            text=True
        )
        self.assertIn("Film Noir", result.stdout)
    
    def test_cli_options(self):
        """Test that CLI options work correctly."""
        # Test the --version option
        result = subprocess.run(
            ["docker", "exec", "kometa-ai-test", "python", "-m", "kometa_ai", "--version"],
            capture_output=True,
            text=True
        )
        self.assertRegex(result.stdout, r"\d+\.\d+\.\d+")
        
        # Test the --dump-config option
        result = subprocess.run(
            ["docker", "exec", "kometa-ai-test", "python", "-m", "kometa_ai", "--dump-config"],
            capture_output=True,
            text=True
        )
        self.assertIn("RADARR_URL", result.stdout)
    
    def test_python_dependencies(self):
        """Test that all required Python dependencies are installed."""
        # Check for key dependencies
        deps_to_check = ["requests", "anthropic", "ruamel.yaml", "unidecode"]
        
        for dep in deps_to_check:
            result = subprocess.run(
                ["docker", "exec", "kometa-ai-test", "python", "-c", 
                f"import {dep}; print({dep}.__version__)"],
                capture_output=True,
                text=True
            )
            # If import succeeds, stdout will contain the version
            self.assertNotIn("ModuleNotFoundError", result.stderr)
    
    def test_non_root_execution(self):
        """Test that the container runs as a non-root user."""
        result = subprocess.run(
            ["docker", "exec", "kometa-ai-test", "id"],
            capture_output=True,
            text=True
        )
        # Should not be running as root (uid=0)
        self.assertNotIn("uid=0", result.stdout)
        self.assertIn("kometa", result.stdout)


class TestDockerComposeConfiguration(unittest.TestCase):
    """Tests for the docker-compose configuration."""
    
    def test_docker_compose_validity(self):
        """Test that docker-compose.yml is valid."""
        result = subprocess.run(
            ["docker-compose", "config"],
            capture_output=True,
            text=True
        )
        self.assertEqual(0, result.returncode)
    
    def test_docker_compose_contains_required_services(self):
        """Test that docker-compose.yml contains required services."""
        with open("docker-compose.yml", "r") as f:
            compose_content = f.read()
        
        self.assertIn("kometa-ai:", compose_content)
        self.assertIn("volumes:", compose_content)
        self.assertIn("environment:", compose_content)
        self.assertIn("healthcheck:", compose_content)
    
    def test_docker_compose_security_practices(self):
        """Test that docker-compose.yml follows security best practices."""
        with open("docker-compose.yml", "r") as f:
            compose_content = f.read()
        
        # Check for use of environment variables for sensitive data
        self.assertIn("RADARR_API_KEY", compose_content)
        self.assertIn("CLAUDE_API_KEY", compose_content)
        
        # Check for proper restart policy
        self.assertIn("restart: unless-stopped", compose_content)


class TestDockerfileCompliance(unittest.TestCase):
    """Tests for Dockerfile compliance with production requirements."""
    
    def test_dockerfile_has_required_elements(self):
        """Test that Dockerfile has required elements."""
        with open("Dockerfile", "r") as f:
            dockerfile_content = f.read()
        
        # Check for multi-stage build
        self.assertIn("AS builder", dockerfile_content)
        
        # Check for pip optimizations
        self.assertIn("PIP_NO_CACHE_DIR", dockerfile_content)
        
        # Check for proper user creation and permissions
        self.assertIn("useradd", dockerfile_content)
        self.assertIn("chown", dockerfile_content)
        
        # Check for labels
        self.assertIn("LABEL", dockerfile_content)
        
        # Check for healthcheck
        self.assertIn("HEALTHCHECK", dockerfile_content)
    
    def test_dockerfile_security_best_practices(self):
        """Test that Dockerfile follows security best practices."""
        with open("Dockerfile", "r") as f:
            dockerfile_content = f.read()
        
        # Check for non-root user
        self.assertIn("USER kometa", dockerfile_content)
        
        # Check for clean-up of build artifacts
        self.assertIn("rm -rf", dockerfile_content)
        
        # Check for minimal dependencies (no dev tools in final image)
        self.assertNotIn("gcc", dockerfile_content.split("AS builder")[1])


if __name__ == "__main__":
    unittest.main()