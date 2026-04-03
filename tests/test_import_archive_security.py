"""
Security tests for archive import (Phase 4).
Verifies protection against Zip Slip (path traversal) and malicious symlinks.
"""
import os
import tarfile
import io
import pytest
import shutil
from tomcat.app import create_app

# Global app instance to avoid re-registering blueprints
_test_app = None

@pytest.fixture
def app():
    global _test_app
    if _test_app is None:
        _test_app = create_app()
        _test_app.config.update({
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
        })
    return _test_app

@pytest.fixture
def client(app):
    return app.test_client()

class TestZipSlipValidation:
    """SEC-01, SEC-02: Archive import must be secure."""

    def test_traversal_aborts_no_write(self, client):
        """An archive with path traversal ('../') should be rejected."""
        # Create a malicious tarball in memory
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w:gz") as tar:
            # Malicious member
            content = b"malicious content"
            tarinfo = tarfile.TarInfo(name="../../outside.txt")
            tarinfo.size = len(content)
            tar.addfile(tarinfo, io.BytesIO(content))
            
            # Also add a valid session file so it doesn't fail early
            session_content = b"tomo_name,thickness,notes\ntomo1,100,test"
            tarinfo = tarfile.TarInfo(name="session.csv")
            tarinfo.size = len(session_content)
            tar.addfile(tarinfo, io.BytesIO(session_content))

        tar_stream.seek(0)
        
        # Upload the malicious archive
        response = client.post(
            '/session/import_archive',
            data={'archive_file': (tar_stream, 'malicious.tar.gz')},
            content_type='multipart/form-data',
            follow_redirects=True
        )
        
        # Check if it was rejected
        # In the current (vulnerable) state, it likely won't be rejected with a specific security message.
        # We expect the fix to flash a specific security error.
        assert b"Security error" in response.data or b"Invalid path" in response.data or b"Illegal member name" in response.data
        
        # Verify that it didn't flash success
        assert b"Successfully imported" not in response.data

    def test_symlink_traversal_rejection(self, client):
        """An archive with a symlink pointing outside should be rejected."""
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w:gz") as tar:
            # Symlink to /etc/passwd (or any absolute path)
            tarinfo = tarfile.TarInfo(name="malicious_link")
            tarinfo.type = tarfile.SYMTYPE
            tarinfo.linkname = "/etc/passwd"
            tar.addfile(tarinfo)
            
            # Valid session
            session_content = b"tomo_name,thickness,notes\ntomo1,100,test"
            tarinfo = tarfile.TarInfo(name="session.csv")
            tarinfo.size = len(session_content)
            tar.addfile(tarinfo, io.BytesIO(session_content))

        tar_stream.seek(0)
        
        response = client.post(
            '/session/import_archive',
            data={'archive_file': (tar_stream, 'malicious_symlink.tar.gz')},
            content_type='multipart/form-data',
            follow_redirects=True
        )
        
        assert b"Security error" in response.data or b"Invalid path" in response.data or b"Illegal member" in response.data
        assert b"Successfully imported" not in response.data

    def test_valid_archive_accepted(self, client, tmp_path, app):
        """A valid archive should still work."""
        # Use a real temp folder for this test to avoid messing with other tests
        upload_dir = tmp_path / "uploads"
        thumb_dir = tmp_path / "thumbnails"
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(thumb_dir, exist_ok=True)

        # We need to temporarily point the app's config to these folders
        # Since config is global in app.py, this is a bit dirty but works for testing
        from tomcat.app import config as app_config
        old_upload = app_config.upload_folder
        old_thumb = app_config.thumbnails_folder
        
        app_config.upload_folder = str(upload_dir)
        app_config.thumbnails_folder = str(thumb_dir)
        app_config.lowmag_folder = str(tmp_path / "lowmag")
        app_config.tiltseries_folder = str(tmp_path / "tiltseries")
        app_config.tomogram_folder = str(tmp_path / "tomogram")

        try:
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w:gz") as tar:
                session_content = b"tomo_name,thickness,notes\ntomo1,100,test"
                tarinfo = tarfile.TarInfo(name="session.csv")
                tarinfo.size = len(session_content)
                tar.addfile(tarinfo, io.BytesIO(session_content))
                
                # Add a thumbnail
                thumb_content = b"fake_png"
                tarinfo = tarfile.TarInfo(name="thumbnails/tomo1.png")
                tarinfo.size = len(thumb_content)
                tar.addfile(tarinfo, io.BytesIO(thumb_content))

            tar_stream.seek(0)
            
            response = client.post(
                '/session/import_archive',
                data={'archive_file': (tar_stream, 'valid.tar.gz')},
                content_type='multipart/form-data',
                follow_redirects=True
            )
            
            assert b"Successfully imported" in response.data
            assert os.path.exists(os.path.join(str(upload_dir), "session.csv"))
            assert os.path.exists(os.path.join(str(thumb_dir), "tomo1.png"))
        finally:
            # Restore old config
            app_config.upload_folder = old_upload
            app_config.thumbnails_folder = old_thumb
