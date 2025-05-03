import os
from setuptools import setup, find_packages

# Read version without importing
with open("kometa_ai/__version__.py", "r") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"')
            break

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as f:
    requirements = f.read().splitlines()

# Create directory structure and py.typed files if needed
for pkg in ['kometa_ai', 
            'kometa_ai/claude', 
            'kometa_ai/common', 
            'kometa_ai/kometa', 
            'kometa_ai/notification', 
            'kometa_ai/radarr', 
            'kometa_ai/state',
            'kometa_ai/utils']:
    # Make sure directory exists
    if not os.path.exists(pkg):
        os.makedirs(pkg, exist_ok=True)
        # Create __init__.py if it doesn't exist
        init_path = os.path.join(pkg, '__init__.py')
        if not os.path.exists(init_path):
            with open(init_path, 'w') as f:
                f.write('"""Auto-generated package init."""\n')
    
    # Create py.typed file (empty file is sufficient)
    py_typed_path = os.path.join(pkg, 'py.typed')
    with open(py_typed_path, 'w') as f:
        pass

setup(
    name="kometa-ai",
    version=version,
    author="tikibozo",
    author_email="tikibozo@users.noreply.github.com",
    description="Claude AI integration for Radarr collections in Kometa",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tikibozo/kometa-ai",
    # Define packages explicitly rather than using find_packages()
    packages=['kometa_ai', 
             'kometa_ai.claude', 
             'kometa_ai.common', 
             'kometa_ai.kometa', 
             'kometa_ai.notification', 
             'kometa_ai.radarr', 
             'kometa_ai.state',
             'kometa_ai.utils'],
    # Include py.typed for each package to signal type checking
    package_data={
        'kometa_ai': ['py.typed'],
        'kometa_ai.state': ['py.typed', '*.py'],
        'kometa_ai.claude': ['py.typed', '*.py'],
        'kometa_ai.common': ['py.typed', '*.py'],
        'kometa_ai.kometa': ['py.typed', '*.py'],
        'kometa_ai.notification': ['py.typed', '*.py'],
        'kometa_ai.radarr': ['py.typed', '*.py'],
        'kometa_ai.utils': ['py.typed', '*.py'],
    },
    # Ensure all package data is included
    include_package_data=True,
    # Ensure dependency links are processed
    dependency_links=[],
    # Set zip_safe to False to ensure all files are unpacked
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "kometa-ai=kometa_ai.__main__:main",
        ],
    },
)