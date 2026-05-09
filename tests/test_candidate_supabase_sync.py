from __future__ import annotations

from casemap.supabase_sync import _derive_candidate_public_path


def test_derive_candidate_public_path_accepts_hklii_url_or_path():
    assert (
        _derive_candidate_public_path({"source_url": "https://www.hklii.hk/en/cases/hkcfa/2025/7"})
        == "/en/cases/hkcfa/2025/7"
    )
    assert (
        _derive_candidate_public_path({"source_url": "/en/cases/hkca/2024/12"})
        == "/en/cases/hkca/2024/12"
    )
    assert _derive_candidate_public_path({"source_url": "https://example.com/not-a-case"}) is None
