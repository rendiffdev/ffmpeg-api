"""
Setup script for Rendiff FFmpeg API
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="rendiff",
    version="1.0.0",
    author="Rendiff",
    author_email="dev@rendiff.dev",
    description="Self-hosted FFmpeg API with multi-storage support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rendiffdev/ffmpeg-api",
    project_urls={
        "Homepage": "https://rendiff.dev",
        "Bug Tracker": "https://github.com/rendiffdev/ffmpeg-api/issues",
        "Documentation": "https://github.com/rendiffdev/ffmpeg-api/blob/main/docs/",
        "Repository": "https://github.com/rendiffdev/ffmpeg-api",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Video :: Conversion",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(),
    python_requires=">=3.12",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.4",
            "pytest-asyncio>=0.23.3",
            "pytest-cov>=4.1.0",
            "black>=23.12.1",
            "flake8>=7.0.0",
            "mypy>=1.8.0",
            "pre-commit>=3.6.0",
        ],
        "gpu": [
            "nvidia-ml-py>=12.535.108",
        ],
    },
    entry_points={
        "console_scripts": [
            "rendiff-api=api.main:main",
            "rendiff-worker=worker.main:main",
            "rendiff-cli=cli.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "rendiff": [
            "config/*.yml",
            "config/*.json",
            "scripts/*.sh",
            "docker/**/Dockerfile",
        ],
    },
)