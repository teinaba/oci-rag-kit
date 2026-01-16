"""
設定管理パッケージ

.envファイルとOCI設定ファイルから設定を読み込み、
アプリケーション全体で使用する設定値を提供します。
"""

from .config_loader import (
    ConfigLoader,
    # 後方互換性のための関数版
    load_config,
    get_db_connection_params,
    get_admin_db_connection_params,
    get_oci_config,
    get_genai_endpoint_from_region,
    get_genai_config,
    get_object_storage_config,
    get_app_config,
    get_genai_client,
    get_object_storage_client,
)

__all__ = [
    # Class
    'ConfigLoader',
    # Functions (backward compatibility)
    'load_config',
    'get_db_connection_params',
    'get_admin_db_connection_params',
    'get_oci_config',
    'get_genai_endpoint_from_region',
    'get_genai_config',
    'get_object_storage_config',
    'get_app_config',
    'get_genai_client',
    'get_object_storage_client',
]
