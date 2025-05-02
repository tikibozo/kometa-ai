# GitHub Actions Workflows for Kometa-AI

This directory contains CI/CD workflows for the Kometa-AI project.

## Workflows

### CI/CD Pipeline

The main workflow (`ci-cd.yml`) provides:

1. **Automated Testing**:
   - Runs linting with flake8
   - Performs type checking with mypy
   - Executes unit and integration tests with pytest
   - Uploads coverage reports to Codecov

2. **Docker Image Building and Publishing**:
   - Builds the Docker image using the optimized Dockerfile
   - Pushes to Docker Hub with appropriate tags
   - Uses caching to speed up builds

## Setting Up Required Secrets

To enable Docker Hub publishing, you must add these repository secrets:

1. Go to your GitHub repository
2. Click on "Settings" tab
3. In the left sidebar, click on "Secrets and variables" > "Actions"
4. Click "New repository secret"
5. Add your secrets one by one:

   For Docker Hub username:
   - Name: `DOCKERHUB_USERNAME`
   - Value: Your Docker Hub username

   For Docker Hub token:
   - Name: `DOCKERHUB_TOKEN` 
   - Value: Your Docker Hub access token (create one at https://hub.docker.com/settings/security)

## Trigger Points

The workflow will automatically run when:
- Code is pushed to the main branch
- Pull requests are opened against main
- Git tags starting with "v" are pushed (for releases)

## Version Tagging

For versioned releases, tag your commit with a version number:

```bash
# Create a tag
git tag v1.0.0

# Push tag to GitHub
git push origin v1.0.0
```

This will trigger a workflow that builds and publishes a Docker image with version tags:
- `yourusername/kometa-ai:1.0.0`
- `yourusername/kometa-ai:1.0`

## Testing Modifications

If you need to modify the workflow, you can test it by creating a pull request or by pushing to a branch.