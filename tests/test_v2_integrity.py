from pathlib import Path
import pytest
from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.dreamcast.image_integrity import validate_source,ImageIntegrityError
from openmenu_gdemu_manager.services.sd_slot_transaction import SdSlotTransactionService
from openmenu_gdemu_manager.ui import workers


def source(tmp_path,name='source',offset=0,sectors=2):
    folder=tmp_path/name;folder.mkdir()
    (folder/'disc.gdi').write_text(f'1\n1 45000 4 2048 "track 03.iso" {offset}\n')
    (folder/'track 03.iso').write_bytes(bytes(offset+2048*sectors))
    return folder


@pytest.mark.parametrize('failure',['missing','empty','partial','outside','bad_count'])
def test_invalid_gdi_reasons(tmp_path,failure):
    folder=source(tmp_path);track=folder/'track 03.iso'
    if failure=='missing':track.unlink()
    elif failure=='empty':track.write_bytes(b'')
    elif failure=='partial':track.write_bytes(bytes(2049))
    elif failure=='outside':(folder/'disc.gdi').write_text('1\n1 45000 4 2048 ../track.iso 0')
    elif failure=='bad_count':(folder/'disc.gdi').write_text('2\n1 45000 4 2048 "track 03.iso" 0')
    with pytest.raises(ImageIntegrityError):validate_source(folder)


def test_quoted_names_and_offsets_valid(tmp_path):validate_source(source(tmp_path,offset=16))


def test_proven_whole_sector_truncation(tmp_path):
    folder=source(tmp_path,sectors=20)
    image=bytearray((folder/'track 03.iso').read_bytes())
    image[16*2048:16*2048+7]=b'\x01CD001\x01'
    image[16*2048+80:16*2048+84]=(40).to_bytes(4,'little')
    (folder/'track 03.iso').write_bytes(image)
    with pytest.raises(ImageIntegrityError,match='filesystem'):validate_source(folder)


@pytest.mark.parametrize('multiple',[False,True])
def test_multisession_addresses_and_split_data_not_falsely_rejected(tmp_path,multiple):
    folder=source(tmp_path,sectors=20)
    image=bytearray((folder/'track 03.iso').read_bytes())
    image[16*2048:16*2048+7]=b'\x01CD001\x01'
    image[16*2048+80:16*2048+84]=(45040 if multiple else 45020).to_bytes(4,'little')
    (folder/'track 03.iso').write_bytes(image)
    if multiple:
        (folder/'disc.gdi').write_text('2\n1 45000 4 2048 "track 03.iso" 0\n2 45030 4 2048 track05.iso 0\n')
        (folder/'track05.iso').write_bytes(bytes(10*2048))
    validate_source(folder)


def test_invalid_addition_rejected_before_deletion_or_registry(tmp_path):
    root=tmp_path/'sd';slot=root/'02';slot.mkdir(parents=True);(slot/'keep.txt').write_text('preserve')
    folder=source(tmp_path);(folder/'track 03.iso').unlink()
    games=[GameItem(2,'Old',folder=slot,pending_delete=True),GameItem(3,'Bad',source_path=str(folder),pending_add=True)]
    service=SdSlotTransactionService(root,'invalid',source_validator=validate_source)
    with pytest.raises(ImageIntegrityError):service.execute(service.build_plan(games),games)
    assert (slot/'keep.txt').read_text()=='preserve'
    assert not (root/'_openmenu_gdemu_manager').exists()


def test_copy_damage_rejected_before_slot_published(tmp_path,monkeypatch):
    from openmenu_gdemu_manager.services import sd_slot_transaction as module
    original=module.copy_game_source
    folder=source(tmp_path);root=tmp_path/'sd';root.mkdir()
    game=GameItem(2,'Game',source_path=str(folder),pending_add=True)
    def damaged(src,dst):
        original(src,dst)
        # Preserve aggregate bytes: the old check alone would accept this.
        (dst/'track 03.iso').rename(dst/'wrong.iso')
    monkeypatch.setattr(module,'copy_game_source',damaged)
    service=SdSlotTransactionService(root,'damage',source_validator=validate_source)
    with pytest.raises(ImageIntegrityError):service.execute(service.build_plan([game]),[game])
    assert not (root/'02').exists()
    assert (service.transaction_dir/'state.json').exists()


def test_valid_copy_preserves_configuration(tmp_path):
    folder=source(tmp_path);root=tmp_path/'sd';root.mkdir();config=root/'GDEMU.ini';config.write_bytes(b'open_time = 150\r\n')
    game=GameItem(2,'Game',source_path=str(folder),pending_add=True,is_new=True)
    service=SdSlotTransactionService(root,'valid',source_validator=validate_source)
    service.execute(service.build_plan([game]),[game])
    validate_source(root/'02')
    assert config.read_bytes()==b'open_time = 150\r\n'


def test_failed_preflight_worker_does_not_log_to_sd(tmp_path):
    folder=source(tmp_path);(folder/'track 03.iso').unlink();root=tmp_path/'sd';root.mkdir()
    worker=workers.SaveChangesWorker(root,[GameItem(2,'Bad',source_path=str(folder),pending_add=True)],{},validate_images=True)
    errors=[];worker.error.connect(errors.append);worker.run()
    assert errors and list(root.iterdir())==[]


@pytest.mark.parametrize('worker_type',['search','bulk'])
@pytest.mark.parametrize('fail',[False,True])
def test_readonly_search_never_writes_sd(worker_type,fail,tmp_path,monkeypatch):
    root=tmp_path/'sd';folder=root/'02';folder.mkdir(parents=True);game=GameItem(2,'Search',folder=folder)
    def search(*args,**kwargs):
        if fail:raise RuntimeError('network test')
        return []
    monkeypatch.setattr(workers,'find_candidates',search)
    monkeypatch.setattr(workers,'load_saved_candidates',lambda _:[])
    def forbidden(*a,**kw):raise AssertionError('SD log attempted')
    called=[]
    monkeypatch.setattr(workers,'append_search_event_for_game',lambda *a,**kw:called.append(a))
    worker=workers.SearchWorker(game,'Search',write_allowed=False) if worker_type=='search' else workers.BulkWorker([game],write_allowed=False)
    worker.run()
    assert called==[] and list(root.rglob('*'))==[folder]


def test_cdi_basic_check_does_not_require_gdi_tracks(tmp_path):
    cdi=tmp_path/'disc.cdi';cdi.write_bytes(b'placeholder for original CDI compatibility')
    validate_source(cdi)
    cdi.write_bytes(b'')
    with pytest.raises(ImageIntegrityError,match='Empty CDI'):validate_source(cdi)


def test_recovery_rejects_existing_damaged_staging_and_can_revert(tmp_path,monkeypatch):
    from openmenu_gdemu_manager.services import sd_slot_transaction as module
    original=module.copy_game_source
    folder=source(tmp_path);root=tmp_path/'sd';root.mkdir()
    game=GameItem(2,'Game',source_path=str(folder),pending_add=True)
    def damaged(src,dst):
        original(src,dst);(dst/'track 03.iso').rename(dst/'wrong.iso')
    monkeypatch.setattr(module,'copy_game_source',damaged)
    service=SdSlotTransactionService(root,'damage',source_validator=validate_source)
    with pytest.raises(ImageIntegrityError):service.execute(service.build_plan([game]),[game])
    # Reconstructed exactly as the original recovery UI, without injection.
    recovery=SdSlotTransactionService(root,'damage')
    assert recovery.can_auto_recover()
    with pytest.raises(ImageIntegrityError):recovery.complete_from_state()
    assert not (root/'02').exists() and recovery._read_state()['stage']=='failed'
    recovery.revert_from_state()
    assert not (root/'02').exists() and recovery._read_state()['stage']=='reverted'


@pytest.mark.parametrize('existing_staging',[False,True])
def test_recovery_validates_source_and_finishes_a_complete_addition(tmp_path,existing_staging):
    from openmenu_gdemu_manager.dreamcast.sd_writer import copy_game_source
    folder=source(tmp_path);root=tmp_path/'sd';root.mkdir()
    game=GameItem(2,'Game',source_path=str(folder),pending_add=True)
    service=SdSlotTransactionService(root,'recover')
    service._write_json('plan.json',service.build_plan([game]).to_dict());service._write_state('planned')
    if existing_staging:copy_game_source(folder,service.add_dir/'02')
    service.complete_from_state();validate_source(root/'02')
    assert service._read_state()['created_slots']==[2]
    # Recovery must preserve ownership even if a later operation needs revert.
    service.revert_from_state();assert not (root/'02').exists()


def test_recovery_invalid_source_is_rejected_before_any_mutation(tmp_path):
    folder=source(tmp_path);(folder/'track 03.iso').unlink()
    root=tmp_path/'sd';root.mkdir()
    game=GameItem(2,'Bad',source_path=str(folder),pending_add=True)
    service=SdSlotTransactionService(root,'recover')
    service._write_json('plan.json',service.build_plan([game]).to_dict());service._write_state('planned')
    before=(service.transaction_dir/'state.json').read_bytes()
    with pytest.raises(ImageIntegrityError):service.complete_from_state()
    assert (service.transaction_dir/'state.json').read_bytes()==before and not (root/'02').exists()


@pytest.mark.parametrize('validate_images',[False,True])
def test_pending_transaction_blocks_worker_without_sd_log(tmp_path,validate_images):
    root=tmp_path/'sd';root.mkdir()
    previous=SdSlotTransactionService(root,'previous');previous._write_state('failed')
    before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    worker=workers.SaveChangesWorker(root,[],{},validate_images=validate_images)
    errors=[];worker.error.connect(errors.append);worker.run()
    assert errors
    assert {p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}==before


def test_pending_transaction_blocks_new_execute_before_directory_creation(tmp_path):
    root=tmp_path/'sd';root.mkdir();folder=source(tmp_path)
    previous=SdSlotTransactionService(root,'previous');previous._write_state('failed')
    game=GameItem(2,'Game',source_path=str(folder),pending_add=True)
    service=SdSlotTransactionService(root,'next',source_validator=validate_source)
    with pytest.raises(RuntimeError):service.execute(service.build_plan([game]),[game])
    assert not service.transaction_dir.exists() and not (root/'02').exists()


def test_late_failure_keeps_addition_ownership_for_rollback(tmp_path,monkeypatch):
    from openmenu_gdemu_manager.services import sd_slot_transaction as module
    folder=source(tmp_path);root=tmp_path/'sd';root.mkdir()
    game=GameItem(2,'Game',source_path=str(folder),pending_add=True)
    service=SdSlotTransactionService(root,'late',source_validator=validate_source)
    def fail(*a):raise OSError('late name failure')
    monkeypatch.setattr(module,'write_name_txt',fail)
    with pytest.raises(OSError):service.execute(service.build_plan([game]),[game])
    assert (root/'02').exists() and service._read_state()['created_slots']==[2]
    service.revert_from_state();assert not (root/'02').exists()


def test_reverting_published_reorder_restores_cycle(tmp_path,monkeypatch):
    from openmenu_gdemu_manager.services import sd_slot_transaction as module
    root=tmp_path/'sd';root.mkdir()
    for number in (2,3):
        slot=root/f'{number:02d}';slot.mkdir();(slot/'disc.cdi').write_bytes(str(number).encode())
    games=[GameItem(3,'Three',folder=root/'03'),GameItem(2,'Two',folder=root/'02')]
    service=SdSlotTransactionService(root,'reorder')
    def fail(*a):raise OSError('late name failure')
    monkeypatch.setattr(module,'write_name_txt',fail)
    with pytest.raises(OSError):service.execute(service.build_plan(games),games)
    service.revert_from_state()
    assert (root/'02'/'disc.cdi').read_bytes()==b'2' and (root/'03'/'disc.cdi').read_bytes()==b'3'


def test_mixed_move_and_add_rollback_never_removes_restored_original(tmp_path,monkeypatch):
    from openmenu_gdemu_manager.services import sd_slot_transaction as module
    root=tmp_path/'sd';slot=root/'03';slot.mkdir(parents=True)
    (slot/'original.txt').write_text('preserve original')
    folder=source(tmp_path)
    games=[GameItem(3,'Original',folder=slot),GameItem(2,'New',source_path=str(folder),pending_add=True)]
    service=SdSlotTransactionService(root,'mixed',source_validator=validate_source)
    def fail(*a):raise OSError('late name failure')
    monkeypatch.setattr(module,'write_name_txt',fail)
    with pytest.raises(OSError):service.execute(service.build_plan(games),games)
    service.revert_from_state()
    assert (slot/'original.txt').read_text()=='preserve original'
    assert not (root/'02').exists() and service._read_state()['stage']=='reverted'


def test_interrupted_rollback_resumes_without_mistaking_restored_folders(tmp_path,monkeypatch):
    from openmenu_gdemu_manager.services import sd_slot_transaction as module
    root=tmp_path/'sd';root.mkdir()
    for number in (2,3):
        slot=root/f'{number:02d}';slot.mkdir();(slot/'disc.cdi').write_bytes(str(number).encode())
    games=[GameItem(3,'Three',folder=root/'03'),GameItem(2,'Two',folder=root/'02')]
    service=SdSlotTransactionService(root,'interrupted')
    def fail(*a):raise OSError('late name failure')
    monkeypatch.setattr(module,'write_name_txt',fail)
    with pytest.raises(OSError):service.execute(service.build_plan(games),games)
    original_rename=Path.rename
    def interrupted(path,target):
        if path==service.temp_dir/'02' and Path(target)==root/'02':raise OSError('interrupted rollback')
        return original_rename(path,target)
    monkeypatch.setattr(Path,'rename',interrupted)
    with pytest.raises(OSError):service.revert_from_state()
    assert service._read_state()['stage']=='recovering_revert'
    assert not service.can_complete_recovery()
    with pytest.raises(RuntimeError):service.complete_from_state()
    monkeypatch.setattr(Path,'rename',original_rename)
    service.revert_from_state()
    assert (root/'02'/'disc.cdi').read_bytes()==b'2' and (root/'03'/'disc.cdi').read_bytes()==b'3'


@pytest.mark.parametrize('payload',[{},[],{'stage':'failed'}, {'stage':'completed','operation_id':'other'}])
def test_missing_state_evidence_requires_manual_recovery(tmp_path,payload):
    import json
    root=tmp_path/'sd';root.mkdir();folder=source(tmp_path)
    game=GameItem(2,'Game',source_path=str(folder),pending_add=True)
    service=SdSlotTransactionService(root,'ambiguous')
    service._write_json('plan.json',service.build_plan([game]).to_dict())
    (service.transaction_dir/'state.json').write_text(json.dumps(payload))
    assert not service.can_auto_recover() and not service.can_complete_recovery()
    with pytest.raises(ValueError):service.complete_from_state()
    with pytest.raises(ValueError):service.revert_from_state()
    assert not (root/'02').exists()
