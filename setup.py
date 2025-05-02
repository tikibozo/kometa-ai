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

setup(
    name="kometa-ai",
    version=version,
    author="tikibozo",
    author_email="tikibozo@users.noreply.github.com",
    description="Claude AI integration for Radarr collections in Kometa",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tikibozo/kometa-ai",
    packages=find_packages(),
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