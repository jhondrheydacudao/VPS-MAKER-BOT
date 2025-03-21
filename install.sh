#!/bin/bash

echo "```                    

████████╗░█████╗░███╗░░██╗██╗░░░██╗██╗██████╗░
╚══██╔══╝██╔══██╗████╗░██║██║░░░██║██║██╔══██╗
░░░██║░░░███████║██╔██╗██║╚██╗░██╔╝██║██████╔╝
░░░██║░░░██╔══██║██║╚████║░╚████╔╝░██║██╔══██╗
░░░██║░░░██║░░██║██║░╚███║░░╚██╔╝░░██║██║░░██║
░░░╚═╝░░░╚═╝░░╚═╝╚═╝░░╚══╝░░░╚═╝░░░╚═╝╚═╝░░╚═╝ 
```"
echo "Welcome To Automated Installer"

echo "Installing python3-pip and docker."
sudo apt update
sudo apt install -y python3-pip docker.io
echo Installed successfully

# Clone the repository
REPO_URL="https://github.com/TS-25/VPS-MAKER-BOT.git"
echo "Cloning the repository..."
git clone "$REPO_URL" || { echo "Failed to clone repository."; exit 1; }

# Navigate into the cloned directory
cd VPS-MAKER-BOT || { echo "Repository folder not found."; exit 1; }

# Prompt for Bot Token
read -p "Enter your Bot Token: " BOT_TOKEN

# Update bot.py with the token
if [[ -f "bot.py" ]]; then
    sed -i "s/TOKEN = '.*'/TOKEN = '$BOT_TOKEN'/" bot.py
    echo "Bot token successfully updated in bot.py."
else
    echo "Error: bot.py not found. Ensure the file exists in the directory."
    exit 1
fi

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt || { echo "Failed to install requirements."; exit 1; }

# Build Docker image
echo "Building Docker image..."
docker build -t ubuntu-22.04-with-tmate . || { echo "Docker build failed."; exit 1; }
echo "Installing Python packages: discord and docker..."
pip3 install discord docker
# Run the bot
echo "Starting the bot..."
python3 bot.py || { echo "Failed to start the bot."; exit 1; }

echo "Setup Complete! The bot is running."
