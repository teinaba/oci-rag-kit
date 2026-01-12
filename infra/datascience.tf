# --- Data Science Project ---
resource "oci_datascience_project" "export_rag_project" {
  compartment_id = var.compartment_ocid
  description    = "Data Science用のプロジェクト"
  display_name   = "rag_project"
}

# --- Data Science Notebook Session ---
resource "oci_datascience_notebook_session" "export_rag_notebook" {
  compartment_id = var.compartment_ocid
  display_name   = "rag_notebook"
  project_id     = oci_datascience_project.export_rag_project.id

  notebook_session_config_details {
    block_storage_size_in_gbs = 50
    shape                     = "VM.Standard.E5.Flex"
    subnet_id                 = oci_core_subnet.private_subnet.id

    notebook_session_shape_config_details {
      memory_in_gbs = 64
      ocpus         = 4
    }
  }
}
