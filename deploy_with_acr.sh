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
CONTAINER_APP_NAME="ca-odmadevycpyl"
APP_SERVICE_NAME="app-odmadevycpyl"
BACKEND_IMAGE_NAME="macae-backend"
FRONTEND_IMAGE_NAME="macae-frontend"
IMAGE_TAG="latest"

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

echo -e "${YELLOW}Step 1: Logging into Azure Container Registry...${NC}"
az acr login --name $ACR_NAME

echo -e "${YELLOW}Step 2: Building backend image in ACR...${NC}"
cd "$PROJECT_ROOT/src/backend"
az acr build \
  --registry $ACR_NAME \
  --image "${BACKEND_IMAGE_NAME}:${IMAGE_TAG}" \
  --file Dockerfile.acr \
  .

echo -e "${YELLOW}Step 3: Building frontend image in ACR...${NC}"
cd "$PROJECT_ROOT/src/frontend"
az acr build \
  --registry $ACR_NAME \
  --image "${FRONTEND_IMAGE_NAME}:${IMAGE_TAG}" \
  --file Dockerfile.acr \
  .

echo -e "${YELLOW}Step 4: Setting ACR credentials for Container App...${NC}"
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)
az containerapp registry set \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --server "${ACR_LOGIN_SERVER}" \
  --username "$ACR_USERNAME" \
  --password "$ACR_PASSWORD"

echo -e "${YELLOW}Step 5: Updating Container App with new backend image...${NC}"
az containerapp update \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image "${ACR_LOGIN_SERVER}/${BACKEND_IMAGE_NAME}:${IMAGE_TAG}"

echo -e "${YELLOW}Step 6: Updating App Service with new frontend image...${NC}"
az webapp config container set \
  --name $APP_SERVICE_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name "${ACR_LOGIN_SERVER}/${FRONTEND_IMAGE_NAME}:${IMAGE_TAG}" \
  --docker-registry-server-url "https://${ACR_LOGIN_SERVER}"

echo -e "${YELLOW}Step 7: Restarting services...${NC}"
az webapp restart \
  --name $APP_SERVICE_NAME \
  --resource-group $RESOURCE_GROUP

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo -e "Backend Image: ${ACR_LOGIN_SERVER}/${BACKEND_IMAGE_NAME}:${IMAGE_TAG}"
echo -e "Backend Container App: $CONTAINER_APP_NAME"
echo -e "Frontend Image: ${ACR_LOGIN_SERVER}/${FRONTEND_IMAGE_NAME}:${IMAGE_TAG}"
echo -e "Frontend App Service: https://${APP_SERVICE_NAME}.azurewebsites.net"
echo ""
echo -e "${YELLOW}To view backend logs:${NC}"
echo -e "  az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow"
echo -e "${YELLOW}To view frontend logs:${NC}"
echo -e "  az webapp log tail --name $APP_SERVICE_NAME --resource-group $RESOURCE_GROUP"
