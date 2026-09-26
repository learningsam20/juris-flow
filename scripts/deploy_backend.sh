#!/usr/bin/env bash
# ==============================================================================
# JurisFlow - Cloud Run Backend Build & Deploy Script
# ==============================================================================
# Builds the backend container image using Google Cloud Build and deploys it
# to Google Cloud Run with Vertex AI, Supabase, Qdrant Cloud, and GCS storage.
# ==============================================================================

set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 1. Load configuration from .env.gcp if it exists
if [ -f ".env.gcp" ]; then
  # shellcheck source=/dev/null
  source ".env.gcp"
fi

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
REPO_NAME="${REPO_NAME:-jurisflow}"
BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-jurisflow-docs}"
SA_EMAIL="${SA_EMAIL:-jurisflow-backend@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/backend:latest"
SERVICE_NAME="jurisflow-backend"
QDRANT_URL="https://30e5e76d-c1b2-417c-b77d-5105128c3be2.australia-southeast1-0.gcp.cloud.qdrant.io:6333"

if [ -z "${PROJECT_ID}" ]; then
  echo -e "${RED}Error: GCP Project ID is not set. Run ./scripts/provision_gcp.sh first.${NC}"
  exit 1
fi

echo -e "${BLUE}=== Building & Deploying JurisFlow Backend to Cloud Run ===${NC}"
echo "Project:    ${PROJECT_ID}"
echo "Region:     ${REGION}"
echo "Image URI:  ${IMAGE_URI}"
echo "Bucket:     ${BUCKET_NAME}"
echo ""

# 2. Build Container using Google Cloud Build (native linux/amd64 build)
echo -e "${BLUE}[1/3] Building container image with Google Cloud Build...${NC}"
gcloud builds submit backend \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE_URI}"

# 3. Deploy to Google Cloud Run
echo -e "${BLUE}[2/3] Deploying service '${SERVICE_NAME}' to Cloud Run...${NC}"

gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --platform="managed" \
  --service-account="${SA_EMAIL}" \
  --memory="1Gi" \
  --cpu="1" \
  --port="5606" \
  --timeout="300" \
  --min-instances="0" \
  --max-instances="5" \
  --allow-unauthenticated \
  --set-env-vars="PORT=5606,JAIL_ENVIRONMENT=production,JAIL_ACCESS_TOKEN_MINUTES=120,JAIL_LLM_PROVIDER=vertex,JAIL_VERTEX_PROJECT=${PROJECT_ID},JAIL_VERTEX_LOCATION=${REGION},JAIL_VERTEX_MODEL=gemini-2.5-flash,JAIL_ASK_LLM_MODEL=gemini-2.5-flash,JAIL_ASK_LLM_MAX_TOKENS=8192,JAIL_LLM_MAX_TOKENS=4096,JAIL_EMBEDDING_PROVIDER=vertex,JAIL_VERTEX_EMBEDDING_MODEL=text-embedding-005,JAIL_VECTOR_PROVIDER=qdrant,JAIL_QDRANT_URL=${QDRANT_URL},JAIL_STORAGE_BACKEND=gcs,JAIL_DOCUMENT_BUCKET=${BUCKET_NAME},JAIL_OCR_PROVIDER=tesseract,JAIL_TTS_ENABLED=true,JAIL_TTS_PROVIDER=edge" \
  --set-secrets="JAIL_SECRET_KEY=jurisflow-secret-key:latest,JAIL_DATABASE_URL=jurisflow-database-url:latest,JAIL_QDRANT_API_KEY=jurisflow-qdrant-api-key:latest"

# 4. Retrieve Service URL and verify
BACKEND_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(status.url)")

echo ""
echo -e "${GREEN}=== Backend Deployment Successful! ===${NC}"
echo -e "Backend Service URL: ${BLUE}${BACKEND_URL}${NC}"
echo ""

# 5. Automatically configure frontend/vercel.json rewrite
echo -e "${BLUE}[3/3] Updating frontend/vercel.json with the backend URL...${NC}"
cat <<EOF > frontend/vercel.json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "${BACKEND_URL}/api/:path*" },
    { "source": "/media/:path*", "destination": "${BACKEND_URL}/media/:path*" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
EOF
echo -e "${GREEN}frontend/vercel.json updated with backend URL!${NC}"

# Also configure firebase.json in case user wants both on GCP
cat <<EOF > firebase.json
{
  "hosting": {
    "public": "frontend/dist",
    "ignore": [
      "firebase.json",
      "**/.*",
      "**/node_modules/**"
    ],
    "rewrites": [
      {
        "source": "/api/**",
        "run": {
          "serviceId": "${SERVICE_NAME}",
          "region": "${REGION}"
        }
      },
      {
        "source": "/media/**",
        "run": {
          "serviceId": "${SERVICE_NAME}",
          "region": "${REGION}"
        }
      },
      {
        "source": "**",
        "destination": "/index.html"
      }
    ]
  }
}
EOF
echo -e "${GREEN}firebase.json updated!${NC}"

echo ""
echo -e "${GREEN}All set! You can now:${NC}"
echo "1. Deploy Frontend to Vercel: cd frontend && vercel (or git push if linked)"
echo "2. OR Deploy Frontend to Firebase Hosting: ./scripts/deploy_frontend.sh"
