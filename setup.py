#!/usr/bin/env python3
"""
Setup script for MORI Sniper Bot
Installs dependencies step by step to avoid conflicts
"""

import subprocess
import sys


def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Failed to install {package}")
        return False


def main():
    print("🎯 Installing MORI Sniper Bot dependencies...")

    # Core dependencies (required)
    core_packages = [
        "aiohttp>=3.8.0",
        "python-dotenv>=1.0.0",
        "loguru>=0.7.0",
        "requests>=2.28.0",
        "aiofiles>=23.0.0"
    ]

    # Blockchain dependencies
    blockchain_packages = [
        "solana>=0.30.0",
        "base58>=2.1.0"
    ]

    # Social media APIs
    social_packages = [
        "python-telegram-bot>=20.0"
    ]

    # Optional dependencies
    optional_packages = [
        "openai>=1.3.0",  # AI analysis
        "discord.py>=2.3.0",  # Discord monitoring
        "tweepy>=4.12.0",  # Twitter monitoring
        "beautifulsoup4>=4.11.0",  # Web scraping
        "aiosqlite>=0.18.0",  # Database
        "psutil>=5.9.0"  # Performance monitoring
    ]

    print("\n📦 Installing core dependencies...")
    for package in core_packages:
        install_package(package)

    print("\n⛓️ Installing blockchain dependencies...")
    for package in blockchain_packages:
        install_package(package)

    print("\n📱 Installing social media APIs...")
    for package in social_packages:
        install_package(package)

    print("\n🔧 Installing optional dependencies...")
    for package in optional_packages:
        if not install_package(package):
            print(f"⚠️ Skipping {package} - you can install it later if needed")

    print("\n✅ Installation complete!")
    print("🚀 You can now run: python main.py")


if __name__ == "__main__":
    main()