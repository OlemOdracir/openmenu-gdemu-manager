from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.ui.main_window import _bulk_selection_map, _menu_consistency_issues, _product_id_corrections


def test_bulk_selection_map_selects_all_slots():
    games = [GameItem(slot=2, name="A"), GameItem(slot=100, name="B")]

    assert _bulk_selection_map(games, True) == {2: True, 100: True}
    assert _bulk_selection_map(games, False) == {2: False, 100: False}


def test_product_id_corrections_only_include_auto_detected_menu_repairs():
    games = [
        GameItem(slot=100, name="Metal Slug", product_id="SLOT100", previous_product_id="SLOT015", save_status="pendiente_guardar"),
        GameItem(slot=7, name="Manual Cover", product_id="T3601M", save_status="pendiente_guardar"),
        GameItem(slot=8, name="New Game", product_id="T3108M", previous_product_id="OLD", pending_add=True, save_status="pendiente_guardar"),
    ]

    assert _product_id_corrections(games) == [games[0]]


def test_menu_consistency_issues_only_include_detected_warnings():
    games = [
        GameItem(slot=4, name="Needs Move", consistency_warnings=["slot_compaction_needed"]),
        GameItem(slot=5, name="Clean"),
        GameItem(slot=6, name="Deleting", pending_delete=True, consistency_warnings=["slot_compaction_needed"]),
    ]

    assert _menu_consistency_issues(games) == [games[0]]
