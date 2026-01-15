terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 7.0"
    }
  }
}

provider "oci" {
  region = var.region
}

# Home region provider for IAM policies (must be created in home region)
provider "oci" {
  alias  = "home"
  region = var.home_region
}
