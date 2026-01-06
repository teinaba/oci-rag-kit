"""
Shared fixtures for E2E tests

Provides real OCI and Oracle Database connections for end-to-end testing.
"""
import pytest
import oracledb
import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from notebooks.config_loader import ConfigLoader


@pytest.fixture(scope="session")
def config_loader():
    """
    ConfigLoader instance for E2E tests

    Loads configuration from .env file in project root.
    Scope: session - shared across all tests to avoid repeated loading.
    """
    config = ConfigLoader()
    config.load_env()
    return config


@pytest.fixture(scope="session")
def db_connection(config_loader):
    """
    Real Oracle Database connection

    Creates a connection that persists for the entire test session.
    Automatically closes connection after all tests complete.
    """
    db_params = config_loader.get_db_params()
    connection = oracledb.connect(**db_params)

    yield connection

    # Cleanup: close connection
    connection.close()


@pytest.fixture
def cleanup_test_documents(db_connection):
    """
    Cleanup fixture for test documents

    Yields a list to collect test document IDs, then deletes them
    from the database after the test completes.

    Usage:
        def test_example(cleanup_test_documents):
            result = pipeline.process_single('test.pdf')
            cleanup_test_documents.append(result.document_id)
            # Test assertions...
            # Cleanup happens automatically after test
    """
    document_ids = []

    yield document_ids

    # Cleanup: delete test documents and their chunks
    if document_ids:
        cursor = db_connection.cursor()
        try:
            for doc_id in document_ids:
                # Delete chunks first (foreign key constraint)
                cursor.execute(
                    "DELETE FROM chunks WHERE document_id = :id",
                    id=doc_id
                )
                # Delete document
                cursor.execute(
                    "DELETE FROM source_documents WHERE document_id = :id",
                    id=doc_id
                )
            db_connection.commit()
        except Exception as e:
            print(f"Warning: Cleanup failed: {e}")
            db_connection.rollback()
        finally:
            cursor.close()


