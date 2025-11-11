# Azure Container Registry (ACR) Deployment Guide

This guide explains how to deploy the Multi-Agent Custom Automation Engine Solution using Azure Container Registry (ACR) for containerized deployments.

## Overview

The `deploy_with_acr.sh` script automates the deployment of both frontend and backend applications to Azure using Azure Container Registry. This approach provides:

- **Container-based deployment** for better consistency across environments
- **Simplified ACR builds** without BuildKit dependencies
- **Separate deployments** for backend (Container App) and frontend (App Service)

## Prerequisites

Before running the deployment script, ensure you have:

1. **Azure CLI** installed and authenticated
   ```bash
   az login
   ```

2. **Correct Azure subscription** selected
   ```bash
   az account set --subscription <subscription-id>
   ```

3. **Required Azure resources** already provisioned:
   - Azure Container Registry: `acrmacae7359`
   - Resource Group: `rg-odmadev`
   - Container App: `ca-odmadevycpyl` (for backend)
   - App Service: `app-odmadevycpyl` (for frontend)

4. **Permissions** to:
   - Push images to ACR
   - Update Container Apps
   - Update App Services

## Architecture

The deployment targets two separate Azure services:

```
┌─────────────────────────────────────────────────┐
│  Azure Container Registry (acrmacae7359)        │
│  ├─ macae-backend:latest                        │
│  └─ macae-frontend:latest                       │
└─────────────────────────────────────────────────┘
              │                    │
              │                    │
              ▼                    ▼
┌──────────────────────┐  ┌──────────────────────┐
│  Container App       │  │  App Service         │
│  ca-odmadevycpyl     │  │  app-odmadevycpyl    │
│  (Backend API)       │  │  (Frontend Web)      │
└──────────────────────┘  └──────────────────────┘
```

## Deployment Steps

### 1. Navigate to Project Root

```bash
cd /workspaces/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator
```

### 2. Make Script Executable

```bash
chmod +x deploy_with_acr.sh
```

### 3. Run Deployment

```bash
./deploy_with_acr.sh
```

## What the Script Does

The deployment script performs the following steps:

### Step 1: ACR Login
```bash
az acr login --name acrmacae7359
```
Authenticates with Azure Container Registry.

### Step 2: Build Backend Image
```bash
cd src/backend
az acr build \
  --registry acrmacae7359 \
  --image macae-backend:latest \
  --file Dockerfile.acr \
  .
```
- Builds the Python backend using `Dockerfile.acr`
- Pushes the image to ACR as `macae-backend:latest`

### Step 3: Build Frontend Image
```bash
cd src/frontend
az acr build \
  --registry acrmacae7359 \
  --image macae-frontend:latest \
  --file Dockerfile.acr \
  .
```
- Builds the React frontend using `Dockerfile.acr`
- Pushes the image to ACR as `macae-frontend:latest`

### Step 4: Set ACR Credentials
```bash
ACR_USERNAME=$(az acr credential show --name acrmacae7359 --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name acrmacae7359 --query passwords[0].value -o tsv)
az containerapp registry set \
  --name ca-odmadevycpyl \
  --resource-group rg-odmadev \
  --server acrmacae7359.azurecr.io \
  --username "$ACR_USERNAME" \
  --password "$ACR_PASSWORD"
```
Retrieves ACR credentials and configures the Container App to authenticate with ACR.

### Step 5: Update Container App (Backend)
```bash
az containerapp update \
  --name ca-odmadevycpyl \
  --resource-group rg-odmadev \
  --image acrmacae7359.azurecr.io/macae-backend:latest
```
Updates the backend Container App with the new image.

### Step 6: Update App Service (Frontend)
```bash
az webapp config container set \
  --name app-odmadevycpyl \
  --resource-group rg-odmadev \
  --docker-custom-image-name acrmacae7359.azurecr.io/macae-frontend:latest \
  --docker-registry-server-url https://acrmacae7359.azurecr.io
```
Configures the frontend App Service to use the new image.

### Step 7: Restart Services
```bash
az webapp restart \
  --name app-odmadevycpyl \
  --resource-group rg-odmadev
```
Restarts the App Service to pull and run the new frontend image.

## Deployment Time

Expected deployment times:
- **Backend build**: ~2 minutes
- **Frontend build**: ~2 minutes
- **Container App update**: ~30 seconds
- **App Service update**: ~10 seconds
- **Total**: ~5 minutes

## Verification

### Check Deployment Status

**Backend (Container App):**
```bash
az containerapp show \
  --name ca-odmadevycpyl \
  --resource-group rg-odmadev \
  --query properties.latestRevisionName
```

**Frontend (App Service):**
```bash
az webapp show \
  --name app-odmadevycpyl \
  --resource-group rg-odmadev \
  --query state
```

### View Logs

**Backend logs (Container App):**
```bash
az containerapp logs show \
  --name ca-odmadevycpyl \
  --resource-group rg-odmadev \
  --follow
```

**Frontend logs (App Service):**
```bash
az webapp log tail \
  --name app-odmadevycpyl \
  --resource-group rg-odmadev
```

### Access Applications

- **Frontend URL**: https://app-odmadevycpyl.azurewebsites.net
- **Backend API**: https://ca-odmadevycpyl.gentlebush-61a50694.japaneast.azurecontainerapps.io

## Troubleshooting

### Issue: "Login failed with error: UNAUTHORIZED"

**Solution:** Ensure you're logged into Azure CLI with correct permissions:
```bash
az login
az account show
```

### Issue: "Failed to provision revision for container app"

**Possible causes:**
1. **Authentication error**: Container App cannot pull from ACR
   - **Fix**: Ensure ACR credentials are set correctly (Step 4)
   
2. **Image not found**: Image tag doesn't exist in ACR
   - **Fix**: Verify image exists: `az acr repository show-tags --name acrmacae7359 --repository macae-backend`

### Issue: Build fails with "BuildKit" errors

**Solution:** The script uses `Dockerfile.acr` files specifically designed for ACR builds without BuildKit features. Ensure you're using these files, not the standard `Dockerfile`.

### Issue: Container App not updating

**Solution:** Check the Container App revision:
```bash
az containerapp revision list \
  --name ca-odmadevycpyl \
  --resource-group rg-odmadev \
  --query "[].{Name:name, Created:properties.createdTime, Active:properties.active}"
```

## Configuration

### Environment-Specific Deployment

To deploy to a different environment, update these variables at the top of `deploy_with_acr.sh`:

```bash
ACR_NAME="your-acr-name"
ACR_LOGIN_SERVER="your-acr-name.azurecr.io"
RESOURCE_GROUP="your-resource-group"
CONTAINER_APP_NAME="your-container-app"
APP_SERVICE_NAME="your-app-service"
```

### Image Tags

By default, the script uses the `latest` tag. To use version-specific tags:

```bash
IMAGE_TAG="v1.2.3"  # Change from "latest"
```

## Docker Files

The deployment uses specialized Dockerfiles:

- **Backend**: `src/backend/Dockerfile.acr`
  - Single-stage Python build
  - UV package manager for dependencies
  - Optimized for ACR build environment

- **Frontend**: `src/frontend/Dockerfile.acr`
  - Multi-stage build (Node → Python → Final)
  - React frontend compilation
  - Python uvicorn server for hosting

## Security Notes

1. **ACR Credentials**: The script retrieves ACR credentials dynamically. These are stored as secrets in the Container App.

2. **Managed Identity**: The Container App uses Azure Managed Identity for accessing other Azure resources (Key Vault, Cosmos DB, etc.).

3. **CORS Configuration**: The Container App is configured to allow requests from the frontend App Service URL.

## Best Practices

1. **Test Locally First**: Build and test Docker images locally before deploying:
   ```bash
   cd src/backend
   docker build -f Dockerfile.acr -t macae-backend:test .
   docker run -p 8000:8000 macae-backend:test
   ```

2. **Use Version Tags**: Instead of `latest`, use semantic versioning:
   ```bash
   IMAGE_TAG="v1.2.3"
   ```

3. **Monitor Deployments**: Always check logs after deployment to ensure services start correctly.

4. **Incremental Deployment**: Deploy backend and frontend separately if needed:
   ```bash
   # Backend only
   cd src/backend && az acr build --registry acrmacae7359 --image macae-backend:latest --file Dockerfile.acr .
   
   # Frontend only
   cd src/frontend && az acr build --registry acrmacae7359 --image macae-frontend:latest --file Dockerfile.acr .
   ```

## Related Documentation

- [Azure Container Registry Documentation](https://docs.microsoft.com/azure/container-registry/)
- [Azure Container Apps Documentation](https://docs.microsoft.com/azure/container-apps/)
- [Azure App Service Documentation](https://docs.microsoft.com/azure/app-service/)
- [Main Deployment Guide](./DeploymentGuide.md)
- [Manual Azure Deployment](./ManualAzureDeployment.md)

## Support

For issues or questions:
1. Check the [Troubleshooting Steps](./TroubleShootingSteps.md)
2. Review Container App/App Service logs
3. Verify all Azure resources are properly configured
4. Ensure you have the required permissions
