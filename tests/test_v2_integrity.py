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
