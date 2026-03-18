"""
Unit tests for platform/skills/media/resize_image.py
Uses a generated test image — no external API calls.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from aiplatform.skills.media.resize_image import resize_to_variants, VARIANTS


@pytest.fixture
def source_image(tmp_path):
    """Create a 2000×2000 solid-colour PNG as the test source."""
    img = Image.new("RGB", (2000, 2000), color=(100, 150, 200))
    path = tmp_path / "test-source.png"
    img.save(path, format="PNG")
    return path


def test_all_variants_created(source_image, tmp_path):
    result = resize_to_variants(source_image, tmp_path / "sized")
    for variant_name in VARIANTS:
        assert variant_name in result
        assert Path(result[variant_name]["png"]).exists()
        assert Path(result[variant_name]["jpg"]).exists()


def test_output_dimensions(source_image, tmp_path):
    result = resize_to_variants(source_image, tmp_path / "sized")
    for variant_name, (target_w, target_h) in VARIANTS.items():
        img = Image.open(result[variant_name]["png"])
        assert img.size == (target_w, target_h), (
            f"{variant_name}: expected {target_w}×{target_h}, got {img.size}"
        )


def test_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        resize_to_variants(tmp_path / "does-not-exist.png", tmp_path / "out")


def test_source_path_in_result(source_image, tmp_path):
    result = resize_to_variants(source_image, tmp_path / "sized")
    assert result["source_path"] == str(source_image)
