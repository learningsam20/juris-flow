#!/usr/bin/env bash
# ==============================================================================
# JurisLab - GCP Provisioning Script
# ==============================================================================
# Sets up GCP infrastructure for JurisLab:
# - Enables Cloud Run, Artifact Registry, Vertex AI, GCS, Secret Manager, Cloud Build
# - Creates GCS bucket for document storage
# - Creates Artifact Registry repository for container images
# - Creates dedicated Service Account with least-privilege IAM roles
# - Populates Google Secret Manager (Secret Key, Supabase DB URL, Qdrant API Key)
# ==============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== JurisLab GCP Provisioning ===${NC}"

# 1. Detect or ask for GCP Project and Region
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || true)
PROJECT_ID="${GCP_PROJECT_ID:-${CURRENT_PROJECT}}"

if [ -z "${PROJECT_ID}" ]; then
  read -rp "Enter your GCP Project ID: " PROJECT_ID
fi

REGION="${GCP_REGION:-us-central1}"
BUCKET_NAME="${GCS_BUCKET_NAME:-${PROJECT_ID}-jurislab-docs}"
REPO_NAME="jurislab"
SA_NAME="jurislab-backend"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo -e "${GREEN}Configuration:${NC}"
echo "  Project ID:        ${PROJECT_ID}"
echo "  Region:            ${REGION}"
echo "  Storage Bucket:    gs://${BUCKET_NAME}"
echo "  Artifact Registry: ${REPO_NAME}"
echo "  Service Account:   ${SA_EMAIL}"
echo ""

gcloud config set project "${PROJECT_ID}"

# 2. Enable Required APIs
echo -e "${BLUE}[1/5] Enabling GCP APIs...${NC}"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com

# 3. Create Artifact Registry Repository if not exists
echo -e "${BLUE}[2/5] Creating Artifact Registry repository...${NC}"
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${REPO_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="JurisLab Docker repository"
  echo -e "${GREEN}Artifact Registry '${REPO_NAME}' created.${NC}"
else
  echo "Artifact Registry repository '${REPO_NAME}' already exists."
fi

# 4. Create GCS Bucket for Document Storage
echo -e "${BLUE}[3/5] Creating GCS bucket for document storage...${NC}"
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access
  echo -e "${GREEN}Bucket 'gs://${BUCKET_NAME}' created.${NC}"
else
  echo "Bucket 'gs://${BUCKET_NAME}' already exists."
fi

# 5. Create Dedicated Service Account & Assign Roles
echo -e "${BLUE}[4/5] Setting up Service Account & IAM roles...${NC}"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="JurisLab Backend Cloud Run Service Account" \
    --description="Least privilege service account for JurisLab"
  echo -e "${GREEN}Service account '${SA_NAME}' created.${NC}"
else
  echo "Service account '${SA_NAME}' already exists."
fi

# Grant Vertex AI user role (to invoke Gemini and text-embedding models)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user" \
  --condition=None >/dev/null

# Grant GCS storage admin on the specific documents bucket
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin" >/dev/null

# Grant Secret Manager accessor role
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None >/dev/null

# 6. Configure Secret Manager Secrets
echo -e "${BLUE}[5/5] Configuring Secret Manager secrets...${NC}"

create_or_update_secret() {
  local secret_name="$1"
  local secret_val="$2"

  if ! gcloud secrets describe "${secret_name}" >/dev/null 2>&1; then
    echo -n "${secret_val}" | gcloud secrets create "${secret_name}" \
      --replication-policy="automatic" \
      --data-file=-
    echo -e "${GREEN}Secret '${secret_name}' created.${NC}"
  else
    echo -n "${secret_val}" | gcloud secrets versions add "${secret_name}" \
      --data-file=-
    echo -e "${YELLOW}Secret '${secret_name}' updated with new version.${NC}"
  fi
}

# Secret Key (32-byte hex for JWT)
SECRET_KEY="${JAIL_SECRET_KEY:-$(openssl rand -hex 32)}"
create_or_update_secret "jurislab-secret-key" "${SECRET_KEY}"

# Qdrant Cloud API Key
DEFAULT_QDRANT_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6ZDkwYzQ3MTktZGE3ZC00ODA0LTg1MjMtMjY0ZmE2MTNhMDFjIn0.GnCpan_jXRTquKVPBOrerANflVS6uFBoWbdTtm1D-EU"
QDRANT_KEY="${JAIL_QDRANT_API_KEY:-${DEFAULT_QDRANT_KEY}}"
create_or_update_secret "jurislab-qdrant-api-key" "${QDRANT_KEY}"

# Supabase Database URL
DB_URL="${JAIL_DATABASE_URL:-}"
if [ -z "${DB_URL}" ]; then
  echo ""
  echo -e "${YELLOW}Enter your Supabase PostgreSQL connection string:${NC}"
  echo "(Format: postgresql+psycopg2://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require)"
  read -rp "Database URL: " DB_URL
fi

if [ -n "${DB_URL}" ]; then
  create_or_update_secret "jurislab-database-url" "${DB_URL}"
else
  echo -e "${RED}Warning: No database URL provided. Remember to populate secret 'jurislab-database-url' before running the app.${NC}"
fi

# Save config export file
CONFIG_FILE=".env.gcp"
cat <<EOF > "${CONFIG_FILE}"
PROJECT_ID=${PROJECT_ID}
REGION=${REGION}
BUCKET_NAME=${BUCKET_NAME}
REPO_NAME=${REPO_NAME}
SA_EMAIL=${SA_EMAIL}
EOF

echo ""
echo -e "${GREEN}=== Provisioning Complete! ===${NC}"
echo "Provisioning parameters saved to ${CONFIG_FILE}."
echo "You can now run: ./scripts/deploy_backend.sh"
