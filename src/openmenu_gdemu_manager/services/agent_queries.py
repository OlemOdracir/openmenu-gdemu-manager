"""Transport-neutral read-only queries for CLI and a possible future MCP adapter.

No GUI, settings migration, network provider or write transaction is started.
The caller selects an explicit destination; no drive enumeration is performed.
"""
import logging
from dataclasses import asdict
from pathlib import Path

from ..dreamcast.cdi import CDIError, inspect_cdi
from ..dreamcast.image_integrity import ImageIntegrityError, validate_source
from ..dreamcast.storage_diagnostics import diagnose_storage

log = logging.getLogger("openmenu_gdemu_manager.agent.queries")

SCHEMA_VERSION = 1
EXIT_CODES = {'checked': 0, 'invalid': 2, 'unsupported': 3, 'unreadable': 4}


def validate_image(path):
    result = {'schema_version': SCHEMA_VERSION, 'operation': 'validate_image',
              'path': str(path), 'read_only': True, 'hardware_verified': False,
              'scope': 'descriptor_and_declared_track_bounds'}
    try:
        path = Path(path).expanduser().resolve()
        result['path'] = str(path)
        if not path.exists():
            raise OSError('Source does not exist')
        if path.is_file() and path.suffix.lower() == '.cdi':
            result['cdi'] = asdict(inspect_cdi(path))
        else:
            validate_source(path)
        result.update(status='checked', issues=[])
    except CDIError as exc:
        result.update(status=exc.category, issues=[{'category': exc.category, 'code': exc.code, 'message': str(exc)}])
    except ImageIntegrityError as exc:
        if isinstance(exc.__cause__, OSError):
            log.warning("Image access failed: path=%s", path, exc_info=True)
            from ..i18n import tr
            result.update(status='unreadable', issues=[{'category': 'unreadable', 'code': 'source_unreadable', 'message': tr('agent.source_unreadable')}])
        else:
            result.update(status='invalid', issues=[{'category': 'invalid', 'code': 'image_structure', 'message': str(exc)}])
    except Exception:
        log.exception("Image validation failed: path=%s", path)
        from ..i18n import tr
        result.update(status='unreadable', issues=[{'category': 'unreadable', 'code': 'source_unreadable', 'message': tr('agent.source_unreadable')}])
    return result


def diagnose_destination(path):
    path = Path(path).expanduser().resolve()
    diagnostic = diagnose_storage(path)
    from ..i18n import tr
    facts = asdict(diagnostic)
    facts.pop('reason')
    facts.pop('menu')  # menu_state and reason_code retain the decision facts.
    facts['message'] = tr('storage.reason.' + diagnostic.reason_code)
    return {'schema_version': SCHEMA_VERSION, 'operation': 'diagnose_destination',
            'path': str(path), 'read_only': True, 'hardware_verified': False,
            'diagnostic': facts}
