from openmenu_gdemu_manager.core.matching import normalize, normalize_product, safe_filename


def test_normalize_removes_noise():
    assert normalize("Sonic Adventure - Disc 1") == "sonic adventure disc 1"


def test_normalize_product_keeps_alnum_uppercase():
    assert normalize_product("T-1234N / rev") == "T1234NREV"


def test_safe_filename_includes_slot_and_png_suffix():
    assert safe_filename(7, "Crazy Taxi!") == "007_Crazy_Taxi.png"
