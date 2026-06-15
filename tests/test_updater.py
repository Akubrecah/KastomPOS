# Tests for KastomPOS Updater logic

import pytest

def is_new_version(current: str, remote: str) -> bool:
    def parse(v):
        import re
        v_clean = re.sub(r'^[^\d]+', '', v)
        v_clean = re.split(r'[^\d.]', v_clean)[0]
        parts = []
        for x in v_clean.split('.'):
            try:
                parts.append(int(x))
            except ValueError:
                parts.append(0)
        return parts

    curr_parsed = parse(current)
    rem_parsed = parse(remote)
    
    max_len = max(len(curr_parsed), len(rem_parsed))
    curr_parsed += [0] * (max_len - len(curr_parsed))
    rem_parsed += [0] * (max_len - len(rem_parsed))
    
    return rem_parsed > curr_parsed

def test_version_comparisons():
    # Standard increments
    assert is_new_version("1.0.0", "1.0.1") is True
    assert is_new_version("1.0.0", "1.1.0") is True
    assert is_new_version("1.0.0", "2.0.0") is True
    
    # Matching versions
    assert is_new_version("1.0.0", "1.0.0") is False
    assert is_new_version("1.2.3", "1.2.3") is False
    
    # Older remote versions
    assert is_new_version("1.0.1", "1.0.0") is False
    assert is_new_version("2.0.0", "1.9.9") is False
    
    # Formatting differences (leading v)
    assert is_new_version("1.0.0", "v1.0.1") is True
    assert is_new_version("v1.0.0", "v1.0.1") is True
    assert is_new_version("v1.0.0", "1.0.1") is True
    
    # Extra segments and suffixes
    assert is_new_version("1.0.0", "1.0.0-beta") is False # parsed as equal
    assert is_new_version("1.0.0", "1.0.1-beta") is True
    
    # Varying length parts
    assert is_new_version("1.0", "1.0.1") is True
    assert is_new_version("1.0.0", "1.0") is False
    assert is_new_version("1.9", "1.10") is True
