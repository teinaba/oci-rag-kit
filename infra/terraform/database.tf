# --- Autonomous AI Database ---
resource "oci_database_autonomous_database" "export_ragdb" {
  compartment_id = var.compartment_ocid
  db_name        = "ragdb"
  display_name   = "ragdb"
  db_version     = "26ai"
  db_workload    = "OLTP"
  admin_password = var.db_admin_password

  # ECPU
  compute_model                       = "ECPU"
  compute_count                       = 2
  data_storage_size_in_gb             = 50
  is_auto_scaling_enabled             = true
  is_auto_scaling_for_storage_enabled = false

  # ライセンスと認証
  license_model               = "LICENSE_INCLUDED"
  is_mtls_connection_required = false
  character_set               = "AL32UTF8"
  ncharacter_set              = "AL16UTF16"

  # ネットワーク制限 (VCNのOCIDを直接参照)
  whitelisted_ips = [
    "${oci_core_vcn.vcn01.id};10.0.1.0/24"
  ]

  # メンテナンス設定
  autonomous_maintenance_schedule_type = "REGULAR"
  backup_retention_period_in_days      = 7

  # 暗号化設定
  encryption_key {
    autonomous_database_provider = "ORACLE_MANAGED"
  }

  # 作成時の状態
  state = "AVAILABLE"

  # ライフサイクル管理（手動での停止・起動を許容する場合）
  lifecycle {
    ignore_changes = [state]
  }
}
