variable "region" { default = "us-chicago-1" } # Chicago or Osaka are supported.
variable "compartment_ocid" { default = "" }
variable "db_admin_password" {
  sensitive = true
  default   = ""
}
