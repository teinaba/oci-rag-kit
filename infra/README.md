# OCI Terraform Infrastructure

Deploy OCI infrastructure for RAG application with Terraform.

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) installed
- [OCI CLI](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm) configured
- Access to OCI compartment

## Quick Start

### 1. Setup Variables

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
region            = "ap-osaka-1"  # or "us-chicago-1"
compartment_ocid  = "ocid1.compartment.oc1..your-actual-ocid"
db_admin_password = "YourSecurePassword123!"
```

### 2. Deploy

```bash
make apply
```

### 3. Destroy (when done)

```bash
make destroy
```

## Available Commands

```bash
make help      # Show all available commands
make test      # Run validation tests (no deployment)
make init      # Initialize Terraform
make plan      # Show execution plan (dry run)
make apply     # Deploy infrastructure
make destroy   # Destroy infrastructure
make clean     # Clean up Terraform files
```

## What Gets Deployed

- **VCN**: Virtual Cloud Network with public and private subnets
- **Autonomous Database**: Oracle Autonomous Database 26ai (OLTP)
- **Data Science**: Project and Notebook Session (ARM-based)
- **Object Storage**: Buckets for FAQ and RAG source data

### Resources Details

| Resource | Type | Description |
|----------|------|-------------|
| VCN | oci_core_vcn | 10.0.0.0/16 CIDR |
| Public Subnet | oci_core_subnet | 10.0.0.0/24 |
| Private Subnet | oci_core_subnet | 10.0.1.0/24 |
| Autonomous DB | oci_database_autonomous_database | 2 ECPUs, 50GB storage |
| Notebook Session | oci_datascience_notebook_session | VM.Standard.A1.Flex (ARM) |
| Object Storage | oci_objectstorage_bucket | 2 buckets (faq, rag-source) |

## Supported Regions

- `us-chicago-1` (Chicago)
- `ap-osaka-1` (Osaka)

## Testing

Run validation without deploying resources:

```bash
make test
```

This will:
1. Initialize Terraform (without backend)
2. Check code formatting
3. Validate configuration
4. Show execution plan

## Security Notes

⚠️ **Important**:
- Never commit `terraform.tfvars` to Git (it contains secrets)
- The `.gitignore` file protects sensitive files automatically
- Use strong passwords (12-30 chars, upper/lower/number required)

## Troubleshooting

### terraform.tfvars not found

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit the file with your values
```

### Authentication errors

Make sure OCI CLI is configured:

```bash
oci setup config
```

### Region not supported

Only `us-chicago-1` and `ap-osaka-1` are tested. Other regions may work but are not guaranteed.

## Resource Costs

Estimated monthly costs (as of 2024):
- Autonomous Database: ~$200-300/month (2 ECPUs, always-on)
- Data Science Notebook: ~$50-100/month (ARM instance)
- VCN & Networking: Free tier eligible
- Object Storage: Pay per usage (~$0.0255/GB/month)

💡 Tip: Stop the notebook session when not in use to reduce costs.

## File Structure

```
.
├── .gitignore                  # Git exclusions
├── Makefile                    # Deployment commands
├── README.md                   # This file
├── terraform.tfvars.example    # Variables template
├── provider.tf                 # OCI provider configuration
├── vars.tf                     # Variable definitions
├── core.tf                     # VCN, subnets, gateways
├── database.tf                 # Autonomous Database
├── datascience.tf              # Data Science resources
└── object_storage.tf           # Object Storage buckets
```

## License

MIT
