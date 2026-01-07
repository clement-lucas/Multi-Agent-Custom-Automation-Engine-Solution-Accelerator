```mermaid
graph TD
    User[Developer] --> Push Code| GH[GitHub Repository]
    
    subgraph "Control Plane (Azure + GitHub)"
        GH -->|Trigger| GHA[GitHub Actions]
        GHA -->|Auth via OIDC| ID[Azure Entra ID]
        GHA -->|Run Job| Runners[Azure Container Apps / AKS Runners]
        Runners -->|State File| TFState[Azure Storage Account]
        Arc[Azure Arc] -->|Monitor| AWS_Res
        Arc -->|Monitor| GCP_Res
    end

    subgraph "Target: Azure"
        Runners -->|Deploy| AzureRes[AKS / App Service]
    end

    subgraph "Target: AWS"
        Runners -->|Deploy| AWSRes[EKS / Lambda]
        ID -.->|Federated Auth| IAM[AWS IAM]
    end

    subgraph "Target: GCP"
        Runners -->|Deploy| GCPRes[GKE / Cloud Run]
        ID -.->|Federated Auth| GIAM[Google IAM]
    end
```