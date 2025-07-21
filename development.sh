#!/bin/bash

set -e  # Exit on any error

echo "🚀 Setting up development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    print_warning "Running as root. Some operations may behave differently."
fi

# Update package lists
print_status "Updating package lists..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update -qq
elif command -v yum &> /dev/null; then
    sudo yum check-update || true
elif command -v dnf &> /dev/null; then
    sudo dnf check-update || true
elif command -v pacman &> /dev/null; then
    sudo pacman -Sy
else
    print_warning "Package manager not detected. Manual installation may be required."
fi

# Install essential tools
print_status "Installing essential development tools..."
if command -v apt-get &> /dev/null; then
    sudo apt-get install -y curl wget git build-essential software-properties-common
elif command -v yum &> /dev/null; then
    sudo yum groupinstall -y "Development Tools"
    sudo yum install -y curl wget git
elif command -v dnf &> /dev/null; then
    sudo dnf groupinstall -y "Development Tools"
    sudo dnf install -y curl wget git
elif command -v pacman &> /dev/null; then
    sudo pacman -S --noconfirm curl wget git base-devel
fi

# Check if Python3 is available
print_status "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_warning "Python3 not found. Installing Python3..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y python3 python3-pip python3-venv python3-dev
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3 python3-pip python3-venv python3-devel
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3 python3-pip python3-venv python3-devel
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm python python-pip python-virtualenv
    else
        print_error "Could not install Python3. Please install manually."
        exit 1
    fi
else
    print_success "Python3 is already installed: $(python3 --version)"
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
    print_warning "pip not found. Installing pip..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y python3-pip
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3-pip
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3-pip
    else
        # Download and install pip manually
        curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        python3 get-pip.py
        rm get-pip.py
    fi
else
    print_success "pip is available"
fi

# Install FFmpeg (required for media processing)
print_status "Checking FFmpeg installation..."
if ! command -v ffmpeg &> /dev/null; then
    print_warning "FFmpeg not found. Installing FFmpeg..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y ffmpeg
    elif command -v yum &> /dev/null; then
        sudo yum install -y ffmpeg
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y ffmpeg
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm ffmpeg
    else
        print_error "Could not install FFmpeg. Please install manually."
        exit 1
    fi
else
    print_success "FFmpeg is already installed: $(ffmpeg -version | head -n1)"
fi

# Create virtual environment
VENV_NAME="venv"
print_status "Creating virtual environment..."

if [ -d "$VENV_NAME" ]; then
    print_warning "Virtual environment already exists. Removing old environment..."
    rm -rf "$VENV_NAME"
fi

python3 -m venv "$VENV_NAME"
print_success "Virtual environment created: $VENV_NAME"

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_NAME/bin/activate"
print_success "Virtual environment activated"

# Upgrade pip
print_status "Upgrading pip..."
python -m pip install --upgrade pip

# Install requirements
if [ -f "requirements.txt" ]; then
    print_status "Installing requirements from requirements.txt..."
    python -m pip install -r requirements.txt
    print_success "Requirements installed successfully"
else
    print_error "requirements.txt not found!"
    exit 1
fi

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    print_status "Installing pre-commit..."
    python -m pip install pre-commit
    print_success "pre-commit installed"
fi

# Install pre-commit hooks
if [ -f ".pre-commit-config.yaml" ]; then
    print_status "Installing pre-commit hooks..."
    pre-commit install
    print_success "Pre-commit hooks installed"
fi

print_success "🎉 Development environment setup complete!"
print_status "To activate the virtual environment in the future, run:"
echo "    source $VENV_NAME/bin/activate"
print_status "To deactivate the virtual environment, run:"
echo "    deactivate"

# Display environment info
echo ""
print_status "Environment Information:"
echo "  Python: $(python --version)"
echo "  Pip: $(pip --version)"
echo "  Virtual Environment: $(pwd)/$VENV_NAME"
if command -v ffmpeg &> /dev/null; then
    echo "  FFmpeg: $(ffmpeg -version | head -n1 | cut -d' ' -f3)"
fi
if command -v redis-server &> /dev/null; then
    echo "  Redis: Available"
fi

echo ""
print_success "You can now start developing! 🚀"