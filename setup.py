import re

from setuptools import setup, find_packages

# Read version without importing (the trailing comment is a
# release-please annotation)
with open("kometa_ai/__version__.py", "r") as f:
    version = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)

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
    packages=find_packages(include=["kometa_ai*"]),
    # py.typed files (committed to git) signal type checking support
    package_data={"": ["py.typed"]},
    include_package_data=True,
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
