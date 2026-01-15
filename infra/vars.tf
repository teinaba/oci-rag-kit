variable "region" { default = "us-chicago-1" } # Chicago or Osaka are supported.
variable "home_region" { default = "us-chicago-1" } # IAM policies must be created in the home region.
variable "compartment_ocid" { default = "" }
variable "db_admin_password" {
  sensitive = true
  default   = ""
}
