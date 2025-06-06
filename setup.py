"""
会社HP自動検索・貼り付けツール セットアップ
"""

from setuptools import setup, find_packages
import os

# requirements.txtからインストール要件を読み込み
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    with open(requirements_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# README.mdから長い説明を読み込み
def read_long_description():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "会社HP自動検索・貼り付けツール - 90%以上の精度で公式HPトップページを検出"

setup(
    name="company-hp-search-tool",
    version="0.1.0",
    author="HP Search Tool Development Team",
    author_email="dev@example.com",
    description="90%以上の精度で公式HPトップページを検出する自動化ツール",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/example/company-hp-search-tool",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-mock>=3.10.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "hp-search-tool=src.main:main",
            "phase1-test=src.phase1_query_test:main",
        ],
    },
    package_data={
        "src": [
            "config/*.yaml",
            "config/*.yml",
            "config/*.json",
        ],
    },
    include_package_data=True,
) 