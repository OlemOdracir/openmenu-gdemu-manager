"""Headless, read-only JSON commands. This module is not an MCP transport."""
import argparse
import json
import logging
import sys

from .services.agent_queries import EXIT_CODES, validate_image, diagnose_destination
from .i18n import set_language, tr
from .app.logger import agent_logging, operation_context


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    preliminary = argparse.ArgumentParser(add_help=False)
    preliminary.add_argument('--language', choices=('en', 'es'), default='en')
    language, _ = preliminary.parse_known_args(argv)
    set_language(language.language)
    parser = argparse.ArgumentParser(description=tr('agent.cli.description'))
    parser.add_argument('--language', choices=('en', 'es'), default='en', help=tr('agent.cli.language'))
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('validate-image', 'diagnose-storage'):
        child = commands.add_parser(name, help=tr('agent.cli.validate' if name == 'validate-image' else 'agent.cli.diagnose'))
        child.add_argument('path', help=tr('agent.cli.path'))
    args = parser.parse_args(argv)
    set_language(args.language)
    with agent_logging() as request_id, operation_context(args.command, request_id):
        try:
            if args.command == 'validate-image':
                result = validate_image(args.path)
                code = EXIT_CODES[result['status']]
            else:
                result = diagnose_destination(args.path)
                code = 0
        except Exception:
            logging.getLogger("openmenu_gdemu_manager.agent.cli").exception("Agent command failed: command=%s path=%s", args.command, args.path)
            result = {'schema_version': 1, 'operation': 'validate_image' if args.command == 'validate-image' else 'diagnose_destination',
                      'path': args.path, 'read_only': True, 'hardware_verified': False,
                      'status': 'unreadable', 'issues': [{'category': 'unreadable', 'code': 'source_unreadable', 'message': tr('agent.source_unreadable')}]}
            code = 4
    result["request_id"] = request_id
    print(json.dumps(result, ensure_ascii=True, default=str))
    return code


if __name__ == '__main__':
    sys.exit(main())
