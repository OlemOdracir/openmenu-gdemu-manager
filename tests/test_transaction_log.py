from openmenu_gdemu_manager.services.transaction_log import (
    append_transaction,
    read_transactions,
    transactions_path,
)


def test_append_transaction_writes_jsonl(tmp_path):
    root = tmp_path / "sd"

    path = append_transaction(
        root,
        {
            "operation_id": "abc123",
            "operation": "save_changes",
            "result": "success",
            "summary": {"added": 1},
            "changes": [{"type": "game_added", "slot": 100, "name": "Test"}],
        },
    )

    assert path == transactions_path(root)
    assert path.exists()
    entries = read_transactions(root)
    assert len(entries) == 1
    assert entries[0]["schema_version"] == 1
    assert entries[0]["operation_id"] == "abc123"
    assert entries[0]["result"] == "success"
    assert entries[0]["summary"]["added"] == 1
