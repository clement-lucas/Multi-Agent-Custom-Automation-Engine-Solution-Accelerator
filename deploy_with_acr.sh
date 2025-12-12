#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Azure Container Registry Deployment ===${NC}"

# Configuration
ACR_NAME="acrmacae7359"
ACR_LOGIN_SERVER="acrmacae7359.azurecr.io"
RESOURCE_GROUP="rg-odmadev"
BACKEND_CONTAINER_APP_NAME="ca-odmadevycpyl"
MCP_CONTAINER_APP_NAME="ca-mcp-odmadevycpyl"
APP_SERVICE_NAME="app-odmadevycpyl"
BACKEND_IMAGE_NAME="macae-backend"
MCP_IMAGE_NAME="macae-mcp"
FRONTEND_IMAGE_NAME="macae-frontend"

# Generate unique tag based on timestamp and git commit (if available)
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "local")
IMAGE_TAG="${TIMESTAMP}-${GIT_COMMIT}"

echo -e "${YELLOW}Image Tag: ${IMAGE_TAG}${NC}"

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# Update version.ts file with current deployment info
echo -e "${YELLOW}Updating version.ts with deployment info...${NC}"
VERSION_FILE="$PROJECT_ROOT/src/frontend/src/version.ts"
cat > "$VERSION_FILE" << EOF
// This file tracks the app version for deployment verification
// Version format: YYYYMMDD-HHMMSS (build timestamp)
// Update APP_VERSION before each deployment to track changes
export const APP_VERSION = '${TIMESTAMP}'; // Auto-updated by deployment script
export const GIT_COMMIT = '${GIT_COMMIT}'; // Git commit hash
EOF
echo -e "${GREEN}Version file updated: ${TIMESTAMP} (${GIT_COMMIT})${NC}"

echo -e "${YELLOW}Step 1: Logging into Azure Container Registry...${NC}"
az acr login --name $ACR_NAME

echo -e "${YELLOW}Step 2: Building backend image in ACR...${NC}"
cd "$PROJECT_ROOT/src/backend"
az acr build \
  --registry $ACR_NAME \
  --image "${BACKEND_IMAGE_NAME}:${IMAGE_TAG}" \
  --image "${BACKEND_IMAGE_NAME}:latest" \
  --file Dockerfile.acr \
  .

echo -e "${YELLOW}Step 3: Building MCP server image in ACR...${NC}"
cd "$PROJECT_ROOT/src/mcp_server"
az acr build \
  --registry $ACR_NAME \
  --image "${MCP_IMAGE_NAME}:${IMAGE_TAG}" \
  --image "${MCP_IMAGE_NAME}:latest" \
  --file Dockerfile \
  .

echo -e "${YELLOW}Step 4: Building frontend image in ACR...${NC}"
cd "$PROJECT_ROOT/src/frontend"
az acr build \
  --registry $ACR_NAME \
  --image "${FRONTEND_IMAGE_NAME}:${IMAGE_TAG}" \
  --image "${FRONTEND_IMAGE_NAME}:latest" \
  --file Dockerfile.acr \
  .

echo -e "${YELLOW}Step 5: Setting ACR credentials for Container Apps...${NC}"
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# Set credentials for backend container app
az containerapp registry set \
  --name $BACKEND_CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --server "${ACR_LOGIN_SERVER}" \
  --username "$ACR_USERNAME" \
  --password "$ACR_PASSWORD"

# Set credentials for MCP container app
az containerapp registry set \
  --name $MCP_CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --server "${ACR_LOGIN_SERVER}" \
  --username "$ACR_USERNAME" \
  --password "$ACR_PASSWORD"

echo -e "${YELLOW}Step 6: Updating backend Container App with new image...${NC}"
az containerapp update \
  --name $BACKEND_CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image "${ACR_LOGIN_SERVER}/${BACKEND_IMAGE_NAME}:${IMAGE_TAG}"

echo -e "${YELLOW}Step 7: Updating MCP Container App with new image...${NC}"
az containerapp update \
  --name $MCP_CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image "${ACR_LOGIN_SERVER}/${MCP_IMAGE_NAME}:${IMAGE_TAG}"

echo -e "${YELLOW}Step 8: Updating App Service with new frontend image...${NC}"
az webapp config container set \
  --name $APP_SERVICE_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name "${ACR_LOGIN_SERVER}/${FRONTEND_IMAGE_NAME}:${IMAGE_TAG}" \
  --docker-registry-server-url "https://${ACR_LOGIN_SERVER}"

echo -e "${YELLOW}Step 9: Restarting services...${NC}"
az webapp restart \
  --name $APP_SERVICE_NAME \
  --resource-group $RESOURCE_GROUP

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo -e "Deployment Tag: ${IMAGE_TAG}"
echo -e ""
echo -e "Backend Images:"
echo -e "  - ${ACR_LOGIN_SERVER}/${BACKEND_IMAGE_NAME}:${IMAGE_TAG}"
echo -e "  - ${ACR_LOGIN_SERVER}/${BACKEND_IMAGE_NAME}:latest (updated)"
echo -e "Backend Container App: $BACKEND_CONTAINER_APP_NAME"
echo -e ""
echo -e "MCP Server Images:"
echo -e "  - ${ACR_LOGIN_SERVER}/${MCP_IMAGE_NAME}:${IMAGE_TAG}"
echo -e "  - ${ACR_LOGIN_SERVER}/${MCP_IMAGE_NAME}:latest (updated)"
echo -e "MCP Container App: $MCP_CONTAINER_APP_NAME"
echo -e ""
echo -e "Frontend Images:"
echo -e "  - ${ACR_LOGIN_SERVER}/${FRONTEND_IMAGE_NAME}:${IMAGE_TAG}"
echo -e "  - ${ACR_LOGIN_SERVER}/${FRONTEND_IMAGE_NAME}:latest (updated)"
echo -e "Frontend App Service: https://${APP_SERVICE_NAME}.azurewebsites.net"
echo ""
echo -e "${YELLOW}To view backend logs:${NC}"
echo -e "  az containerapp logs show --name $BACKEND_CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow"
echo -e "${YELLOW}To view MCP server logs:${NC}"
echo -e "  az containerapp logs show --name $MCP_CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow"
echo -e "${YELLOW}To view frontend logs:${NC}"
echo -e "  az webapp log tail --name $APP_SERVICE_NAME --resource-group $RESOURCE_GROUP"
