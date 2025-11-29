#!/bin/bash

# =============================================================================
# Gemini API Integration Quick Start Script
# =============================================================================
#
# This script automates the setup process for Gemini API integration
#
# Usage: bash quickstart.sh
#
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Gemini API Integration Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print step
print_step() {
    echo -e "${GREEN}[STEP $1]${NC} $2"
}

# Function to print error
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check Python installation
print_step "1" "Checking Python installation..."
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version)
    echo "   ✓ $PYTHON_VERSION"
else
    print_error "Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Step 2: Check pip installation
print_step "2" "Checking pip installation..."
if command_exists pip3; then
    PIP_VERSION=$(pip3 --version)
    echo "   ✓ pip is installed"
else
    print_error "pip is not installed. Please install pip."
    exit 1
fi

# Step 3: Create virtual environment (optional but recommended)
print_step "3" "Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   ✓ Virtual environment created"
else
    echo "   ℹ Virtual environment already exists"
fi

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "   ✓ Virtual environment activated"
fi

# Step 4: Install required packages
print_step "4" "Installing required packages..."
echo "   Installing google-generativeai..."
pip install google-generativeai --quiet
echo "   ✓ google-generativeai installed"

echo "   Installing python-dotenv..."
pip install python-dotenv --quiet
echo "   ✓ python-dotenv installed"

# Install other requirements if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "   Installing other dependencies..."
    pip install -r requirements.txt --quiet
    echo "   ✓ All dependencies installed"
fi

# Step 5: Create .env file
print_step "5" "Setting up environment file..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "   ✓ Created .env from .env.example"
    else
        cat > .env << EOF
# Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# Django Configuration
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=change-this-in-production
EOF
        echo "   ✓ Created .env file"
    fi
else
    echo "   ℹ .env file already exists"
fi

# Step 6: Check .gitignore
print_step "6" "Updating .gitignore..."
if [ ! -f ".gitignore" ]; then
    echo ".env" > .gitignore
    echo "   ✓ Created .gitignore"
else
    if ! grep -q "^\.env$" .gitignore; then
        echo ".env" >> .gitignore
        echo "   ✓ Added .env to .gitignore"
    else
        echo "   ℹ .env already in .gitignore"
    fi
fi

# Step 7: Backup old evaluation file
print_step "7" "Backing up existing files..."
if [ -f "quiz/descriptive_evaluation.py" ]; then
    if [ ! -f "quiz/descriptive_evaluation_backup.py" ]; then
        cp quiz/descriptive_evaluation.py quiz/descriptive_evaluation_backup.py
        echo "   ✓ Backed up descriptive_evaluation.py"
    else
        echo "   ℹ Backup already exists"
    fi
fi

# Step 8: Check if Gemini files are in place
print_step "8" "Checking integration files..."
FILES_NEEDED=("test_api.py" "descriptive_evaluation_gemini.py")
MISSING_FILES=()

for file in "${FILES_NEEDED[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    echo "   ✓ All integration files present"
else
    print_warning "Missing files: ${MISSING_FILES[*]}"
    echo "   Please ensure you have the Gemini integration files."
fi

# Step 9: Prompt for API key
print_step "9" "API Key Setup..."
echo ""
echo "   To complete setup, you need a Gemini API key."
echo "   Get it from: ${BLUE}https://makersuite.google.com/app/apikey${NC}"
echo ""
read -p "   Do you have your Gemini API key? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "   Enter your Gemini API key: " API_KEY
    if [ ! -z "$API_KEY" ]; then
        # Update .env file
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/GEMINI_API_KEY=.*/GEMINI_API_KEY=$API_KEY/" .env
        else
            # Linux
            sed -i "s/GEMINI_API_KEY=.*/GEMINI_API_KEY=$API_KEY/" .env
        fi
        echo "   ✓ API key saved to .env"
    fi
else
    print_warning "Please add your API key to .env manually before testing"
fi

# Step 10: Run tests
echo ""
print_step "10" "Running API tests..."
if [ -f "test_api.py" ]; then
    read -p "   Would you like to test the API now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        python test_api.py
    else
        echo "   ⏭ Skipping API test. Run 'python test_api.py' manually when ready."
    fi
else
    print_warning "test_api.py not found. Cannot run tests."
fi

# Final summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup Complete! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Ensure your .env file has the correct GEMINI_API_KEY"
echo "   ${YELLOW}nano .env${NC}"
echo ""
echo "2. Test the API integration:"
echo "   ${YELLOW}python test_api.py${NC}"
echo ""
echo "3. Update your Django views to use Gemini:"
echo "   - Replace HUGGINGFACE_API_KEY with GEMINI_API_KEY"
echo "   - Import from descriptive_evaluation_gemini.py"
echo ""
echo "4. Run Django migrations (if needed):"
echo "   ${YELLOW}python manage.py migrate${NC}"
echo ""
echo "5. Start the development server:"
echo "   ${YELLOW}python manage.py runserver${NC}"
echo ""
echo "For detailed instructions, see: ${BLUE}GEMINI_SETUP.md${NC}"
echo ""

# Deactivate virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate 2>/dev/null || true
fi