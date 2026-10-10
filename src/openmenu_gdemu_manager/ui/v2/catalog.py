"""Packaged design resources and application i18n; no fixtures or sample covers."""
import json
from pathlib import Path
from ...i18n import tr as app_tr

REFERENCE = Path(__file__).resolve().parents[2] / 'resources/v2'
TOKENS = json.loads((REFERENCE/'tokens.json').read_text(encoding='utf-8'))
ACTIONS = json.loads((REFERENCE/'actions.json').read_text(encoding='utf-8'))


def tr(key, **values):
    return app_tr('v2.'+key, **values)


def action_label(key):
    return app_tr('v2.action.'+key)


def variant(item):
    if 'variant_index' in item:
        return tr('local_variant',count=item['variant_index'])
    return tr('source_real',source=item.get('provider',''),score=item.get('score',0))
