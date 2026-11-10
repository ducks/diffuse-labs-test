"""Recognize a failed harness-supplied root disk, not an application timeout."""
import re

def root_disk_failure(text):
    return bool(re.search(r'\b(?:Buffer )?I/O error\b[^\n]*\b(?:dev|device) vda\b',text))
