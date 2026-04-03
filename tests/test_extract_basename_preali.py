"""
Tests for extract_basename() _preali suffix stripping.

These tests cover the fix for BUG-03: _preali.mrc files creating duplicate
catalogue entries. Before the fix, extract_basename('tomo001_preali.mrc')
returned 'tomo001_preali' instead of 'tomo001'.
"""
import pytest
from tomcat.utils.file_utils import extract_basename


class TestExtractBasenamePreali:
    """Tests that _preali suffix is stripped to produce canonical tomo name."""

    def test_preali_mrc_returns_canonical(self):
        """_preali.mrc must strip to same canonical name as _rec.mrc."""
        assert extract_basename('tomo001_preali.mrc') == 'tomo001'

    def test_preali_no_extension_returns_canonical(self):
        """_preali without extension must strip to canonical name."""
        assert extract_basename('tomo001_preali') == 'tomo001'

    def test_preali_and_rec_produce_same_key(self):
        """Both _preali.mrc and _rec.mrc must produce the same deduplication key."""
        assert extract_basename('tomo001_rec.mrc') == extract_basename('tomo001_preali.mrc')

    # Regression tests — existing behavior must be preserved

    def test_rec_mrc_unchanged(self):
        assert extract_basename('tomo001_rec.mrc') == 'tomo001'

    def test_ali_mrc_unchanged(self):
        assert extract_basename('tomo001_ali.mrc') == 'tomo001'

    def test_plain_mrc_unchanged(self):
        assert extract_basename('tomo001.mrc') == 'tomo001'

    def test_bin_suffix_unchanged(self):
        assert extract_basename('tomo001_bin8') == 'tomo001'
