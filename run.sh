#!/bin/bash

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

echo "Starting ArtStation View Booster..."

# Check if Python is installed
if ! command_exists python3; then
  echo "Python 3 is not installed. Please install Python 3 first."
  exit 1
fi

# Check if uv is installed
if ! command_exists uv; then
  echo "Installing uv package manager..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  
  # Add uv to the current PATH
  export PATH="$HOME/.cargo/bin:$PATH"
  
  echo "uv installed successfully."
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  uv venv
fi

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
  echo "Installing dependencies..."
  uv pip install -r requirements.txt
else
  # Install playwright if not in requirements
  echo "Installing playwright..."
  uv pip install playwright
  playwright install chromium
fi

# Run the application
echo "Running ArtStation View Booster..."
uv run main.py 