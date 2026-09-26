#!/usr/bin/env bash
# ==============================================================================
# JurisLab - Frontend Deploy Script (Vercel or Firebase Hosting)
# ==============================================================================

set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== Building & Deploying JurisLab Frontend ===${NC}"

# 1. Build frontend dist
echo -e "${BLUE}[1/2] Installing dependencies and building production bundle...${NC}"
cd frontend
npm ci
npm run build
cd ..

# 2. Deploy Choice
echo ""
echo -e "${YELLOW}Choose your deployment target:${NC}"
echo "1) Vercel (CLI: 'vercel --prod')"
echo "2) Firebase Hosting ('firebase deploy --only hosting')"
read -rp "Select [1 or 2]: " TARGET

if [ "${TARGET}" = "1" ]; then
  echo -e "${BLUE}[2/2] Deploying to Vercel...${NC}"
  cd frontend
  if command -v vercel >/dev/null 2>&1; then
    vercel --prod
  else
    npx vercel --prod
  fi
  cd ..
elif [ "${TARGET}" = "2" ]; then
  echo -e "${BLUE}[2/2] Deploying to Firebase Hosting...${NC}"
  if command -v firebase >/dev/null 2>&1; then
    firebase deploy --only hosting
  else
    npx -y firebase-tools deploy --only hosting
  fi
else
  echo "Build complete in frontend/dist. You can manually deploy to your chosen provider."
fi

echo -e "${GREEN}Frontend deployment process completed!${NC}"
