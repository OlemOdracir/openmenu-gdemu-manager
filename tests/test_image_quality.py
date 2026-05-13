from PIL import Image

from openmenu_gdemu_manager.core.image_quality import analyze_image


def test_openmenu_target_size_is_maximum_useful_quality():
    report = analyze_image(Image.new("RGB", (256, 256), "#3366aa"))

    assert report.label == "Alta"
    assert report.score == 100
    assert report.accepted


def test_larger_than_openmenu_target_is_not_penalized_by_resolution():
    report = analyze_image(Image.new("RGB", (512, 512), "#3366aa"))

    assert report.label == "Alta"
    assert report.score == 100
    assert report.accepted


def test_slightly_below_openmenu_target_is_acceptable():
    report = analyze_image(Image.new("RGB", (240, 240), "#3366aa"))

    assert report.label == "Aceptable"
    assert report.score == 75
    assert report.accepted


def test_low_resolution_below_openmenu_target_is_low_quality():
    report = analyze_image(Image.new("RGB", (220, 220), "#3366aa"))

    assert report.label == "Baja"
    assert report.score == 45
    assert report.accepted
