data "oci_objectstorage_namespace" "export_namespace" {
  compartment_id = var.compartment_ocid
}

# --- Object Storage ---
# FAQファイル用
resource "oci_objectstorage_bucket" "export_faq" {
  access_type    = "NoPublicAccess"
  auto_tiering   = "Disabled"
  compartment_id = var.compartment_ocid
  defined_tags = {
  }
  freeform_tags = {
  }
  metadata = {
  }
  name                  = "faq"
  namespace             = data.oci_objectstorage_namespace.export_namespace.namespace
  object_events_enabled = "false"
  storage_tier          = "Standard"
  versioning            = "Disabled"
}

# --- Object Storage ---
# RAGソースドキュメント用
resource "oci_objectstorage_bucket" "export_rag-source" {
  access_type    = "NoPublicAccess"
  auto_tiering   = "Disabled"
  compartment_id = var.compartment_ocid
  defined_tags = {
  }
  freeform_tags = {
  }
  metadata = {
  }
  name                  = "rag-source"
  namespace             = data.oci_objectstorage_namespace.export_namespace.namespace
  object_events_enabled = "false"
  storage_tier          = "Standard"
  versioning            = "Disabled"
}
