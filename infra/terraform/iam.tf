# --- IAM Policy for Data Science ---
# IAM policies must be created in the home region
resource "oci_identity_policy" "data_science_policy" {
  provider       = oci.home
  compartment_id = var.compartment_ocid
  name           = "data-science-policy"
  description    = "Policy for Data Science service"
  statements = [
    # NoteboookセッションをVCN内に作成するためのポリシー
    "allow service datascience to use virtual-network-family in compartment id ${var.compartment_ocid}"
  ]
}
