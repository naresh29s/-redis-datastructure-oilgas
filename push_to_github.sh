#!/bin/bash

# ============================================================================
# Push Oil & Gas Redis Demo to GitHub
# ============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Preparing to push Oil & Gas Redis Demo to GitHub${NC}"
echo -e "${BLUE}====================================================${NC}"
echo ""

# GitHub repository URL
GITHUB_REPO="https://github.com/naresh29s/-redis-datastructure-oilgas"

# Step 1: Verify .env is not being tracked
echo -e "${YELLOW}🔒 Step 1: Verifying security...${NC}"

if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: .env file not found!${NC}"
    echo -e "${YELLOW}Please create .env from .env.example first:${NC}"
    echo "  cp .env.example .env"
    exit 1
fi

if [ ! -f .gitignore ]; then
    echo -e "${RED}❌ Error: .gitignore file not found!${NC}"
    exit 1
fi

# Check if .env is in .gitignore
if grep -q "^\.env$" .gitignore; then
    echo -e "${GREEN}✅ .env is properly gitignored${NC}"
else
    echo -e "${RED}❌ Error: .env is not in .gitignore!${NC}"
    exit 1
fi

# Step 2: Initialize git repository
echo ""
echo -e "${YELLOW}📦 Step 2: Initializing Git repository...${NC}"

if [ -d .git ]; then
    echo -e "${BLUE}ℹ️  Git repository already initialized${NC}"
else
    git init
    echo -e "${GREEN}✅ Git repository initialized${NC}"
fi

# Step 3: Configure git (if needed)
echo ""
echo -e "${YELLOW}⚙️  Step 3: Configuring Git...${NC}"

# Check if user name is set
if ! git config user.name > /dev/null 2>&1; then
    echo -e "${YELLOW}Please enter your name for Git commits:${NC}"
    read -p "Name: " git_name
    git config user.name "$git_name"
fi

# Check if user email is set
if ! git config user.email > /dev/null 2>&1; then
    echo -e "${YELLOW}Please enter your email for Git commits:${NC}"
    read -p "Email: " git_email
    git config user.email "$git_email"
fi

echo -e "${GREEN}✅ Git configured${NC}"
echo -e "   Name: $(git config user.name)"
echo -e "   Email: $(git config user.email)"

# Step 4: Add remote repository
echo ""
echo -e "${YELLOW}🔗 Step 4: Adding GitHub remote...${NC}"

# Check if remote already exists
if git remote | grep -q "^origin$"; then
    current_remote=$(git remote get-url origin)
    if [ "$current_remote" != "$GITHUB_REPO" ]; then
        echo -e "${YELLOW}⚠️  Remote 'origin' exists with different URL: $current_remote${NC}"
        read -p "Update to $GITHUB_REPO? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git remote set-url origin "$GITHUB_REPO"
            echo -e "${GREEN}✅ Remote updated${NC}"
        fi
    else
        echo -e "${GREEN}✅ Remote already configured correctly${NC}"
    fi
else
    git remote add origin "$GITHUB_REPO"
    echo -e "${GREEN}✅ Remote added: $GITHUB_REPO${NC}"
fi

# Step 5: Stage files
echo ""
echo -e "${YELLOW}📝 Step 5: Staging files...${NC}"

git add .

# Show what will be committed (excluding .env)
echo -e "${BLUE}Files to be committed:${NC}"
git status --short | head -20
echo ""

# Verify .env is NOT staged
if git status --short | grep -q "\.env$"; then
    echo -e "${RED}❌ ERROR: .env file is staged! This should not happen!${NC}"
    echo -e "${RED}Aborting to prevent credential leak.${NC}"
    exit 1
else
    echo -e "${GREEN}✅ .env is NOT staged (credentials are safe)${NC}"
fi

# Step 6: Create commit
echo ""
echo -e "${YELLOW}💾 Step 6: Creating commit...${NC}"

git commit -m "Initial commit: Oil & Gas Redis Enterprise Demo

- Real-time digital twin system for oil & gas operations
- Redis Enterprise features: Geospatial, Streams, JSON, Search
- 14 field assets with live sensor data simulation
- Interactive dashboard with maps and analytics
- Secure credential management with .env
- Comprehensive documentation and setup guides"

echo -e "${GREEN}✅ Commit created${NC}"

# Step 7: Push to GitHub
echo ""
echo -e "${YELLOW}🚀 Step 7: Pushing to GitHub...${NC}"
echo -e "${BLUE}Repository: $GITHUB_REPO${NC}"
echo ""

read -p "Ready to push to GitHub? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Push to main branch
    git branch -M main
    git push -u origin main
    
    echo ""
    echo -e "${GREEN}🎉 SUCCESS! Project pushed to GitHub!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}📍 Repository URL:${NC}"
    echo -e "   $GITHUB_REPO"
    echo ""
    echo -e "${BLUE}🔗 View on GitHub:${NC}"
    echo -e "   https://github.com/naresh29s/-redis-datastructure-oilgas"
    echo ""
    echo -e "${YELLOW}📋 Next Steps:${NC}"
    echo "   1. Visit the repository on GitHub"
    echo "   2. Verify the README.md displays correctly"
    echo "   3. Check that .env is NOT in the repository"
    echo "   4. Add a repository description and topics"
    echo "   5. Consider adding a LICENSE file"
    echo ""
else
    echo -e "${YELLOW}⚠️  Push cancelled. You can push later with:${NC}"
    echo "   git push -u origin main"
fi

