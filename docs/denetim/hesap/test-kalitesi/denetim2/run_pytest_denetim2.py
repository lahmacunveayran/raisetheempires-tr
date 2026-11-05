"""Launcher for pytest with a unique argv[0] (tendo's single-instance lock is named after argv[0])."""
import sys
import pytest
sys.exit(pytest.main(sys.argv[1:]))
