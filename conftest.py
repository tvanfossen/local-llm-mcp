"""
Pytest configuration for co-located tests in schema-compliant structure.
"""

import sys
from pathlib import Path

import pytest


def pytest_collect_file(parent, file_path):
    """Custom test collection for co-located tests"""
    if file_path.suffix == ".py" and file_path.name.startswith("test_"):
        return pytest.Module.from_parent(parent, path=file_path)


def pytest_configure(config):
    """Configure pytest for co-located test structure"""
    # Add src/ to Python path for imports
    src_path = Path(__file__).parent / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))

    # Configure test discovery to find co-located tests
    config.option.testmon_off = True  # Disable testmon for now


def pytest_collection_modifyitems(config, items):
    """Modify test items to handle co-located structure"""
    for item in items:
        # Add markers based on test location
        test_path = Path(item.fspath)
        parts = test_path.parts

        if "src" in parts:
            # Extract domain/category for markers
            src_idx = parts.index("src")
            if len(parts) > src_idx + 2:
                domain = parts[src_idx + 1]
                category = parts[src_idx + 2]

                # Add markers for filtering
                item.add_marker(pytest.mark.unit)
                item.add_marker(getattr(pytest.mark, domain))
                item.add_marker(getattr(pytest.mark, f"{domain}_{category}"))


@pytest.fixture(scope="session")
def src_root():
    """Provide path to src/ directory"""
    return Path(__file__).parent / "src"


@pytest.fixture(scope="session")
def project_root():
    """Provide path to project root"""
    return Path(__file__).parent
