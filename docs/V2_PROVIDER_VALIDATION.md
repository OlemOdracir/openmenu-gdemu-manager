# V2 opt-in public provider validation

Executed on 2026-10-09 from the local Python environment on Windows.
`OPENMENU_RUN_INTEGRATION=1 python -m pytest tests/test_community_api_integration.py`
completed with **5 passed**, 0 failed, in 20.35 seconds.

| Check | Result | Scope |
| --- | --- | --- |
| Community API health | PASS | Real public HTTPS endpoint. |
| Community API search/proxied media | PASS | Search returned images; response contained no upstream credential fields; proxied media responded with image content. |
| OpenMenu provider | PASS | Production provider found candidates for Crazy Taxi and the production downloader/Pillow decoder loaded one RGB image. |
| Libretro provider | PASS | Same production search/download/decode path, with isolated catalogue/image cache. |
| Community API provider | PASS | Same production search/download/decode path, using the real application client. |

Tests use synthetic GameItem metadata and freshly isolated local caches. They do
not read personal provider settings, use private credentials, scan a physical SD,
select/save covers or publish downloaded images. Runtime XML and downloaded
samples remain private ignored artifacts. The report uses counts rather than
library paths or image bytes.

This records availability at that time, not ongoing uptime or every query/region.
Manual six-candidate selection, palette comparison and real SD writes are separate
checks. Direct ScreenScraper or other credentialed providers are pending only when
the user enables/configures them. The ordinary validation harness remains offline
and skips these tests deliberately; it links here instead of misreporting their
standalone evidence.
