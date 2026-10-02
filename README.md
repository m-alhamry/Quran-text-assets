# Quran text assets

A small static JSON API for complete QuranEnc tafsirs and translations. No API key, application server, database, advertising or analytics is included.

Initial publication: **32 editions in 19 languages**, including four complete Arabic tafsirs: Al-Muyassar, Al-Mukhtasar, Al-Yaseer and An-Nafahat Al-Makkiyyah. Each package contains **114 surahs and 6,236 verse records**, with the original text and footnotes. Completeness here means structural coverage and nonempty entries, not an independent scholarly certification.

## Read the catalogue

- [Primary catalogue](https://raw.githubusercontent.com/m-alhamry/Quran-text-assets/main/api/v1/catalog.json)
- [CDN fallback](https://cdn.jsdelivr.net/gh/m-alhamry/Quran-text-assets@main/api/v1/catalog.json)

Fetch the catalogue, select an enabled edition, then download one of its `urls`. Verify `sizeBytes` and the SHA-256 of the **compressed** bytes before decompressing. Enforce `uncompressedBytes`, validate the payload and only then replace an existing offline copy. Packages have immutable, version-and-hash filenames. GitHub/CDN hosting is best-effort, not a service-level guarantee; keep a bundled catalogue and previously validated downloads.

Catalogue protocol: `schemaVersion: 1`, `readerVersion: 1`, increasing `revision`. Each edition records its permanent `id`, official `sourceKey`, language, title, author/organisation credit, version, source URL, source notice (`transcript`), availability, and package hashes/lengths. `legacyIds` are migration hints for the companion app, never proof of byte-identical editions. Existing downloaded editions retain their original IDs and attribution.

Package protocol:

```json
{"schemaVersion":1,"edition":{"id":"…","source":"QuranEnc.com","version":"…"},"verses":{"1":{"1":{"text":"…","footnotes":"…"}}}}
```

Text/footnotes may contain upstream HTML formatting. Preserve the source data. A reader may render the formatting safely but must retain the text, references, footnotes and credit; never execute HTML scripts.

## Content permission and attribution

The content is provided by **QuranEnc.com** under its published reuse conditions. It is **not relicensed as MIT, public domain or CC0** by this repository.

- [Official QuranEnc API and usage terms](https://quranenc.com/en/home/api/)
- [Official IslamHouse API hub permission policy](https://github.com/IslamHouse-API/multilingual-quran-hadith-islamic-content-database-api-hub)
- [Policy snapshot used for this publication](SOURCE_POLICY.md), retrieved 2026-10-02.

The published policy permits downloading, app integration, republication, and commercial/non-commercial use without prior permission **subject to its conditions**. Preserve the original text, footnotes, attribution and version; update copies when upstream releases corrections. Report scholarly/linguistic issues to the source instead of editing the attributed text. Do not imply official endorsement or display inappropriate advertising alongside it. Follow the complete current source terms; this summary does not replace them. The companion app displays no ads in its Quran feature.

The repository's Python maintenance code is licensed separately under [MIT](scripts/LICENSE). That license does not cover the Quran content, source notices or policy snapshot.

## Maintain the catalogue

Python 3.11+ and curl are sufficient; no Python dependencies or secrets are required.

```sh
python3 scripts/build_catalog.py validate
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/build_catalog.py check-updates
```

To publish an update:

1. Review the current source permissions and official edition metadata; update `editions.json` with the exact source version. Keep IDs stable for the same work. Give a different author/work a new ID.
2. Run `python3 scripts/build_catalog.py build --refresh`. This fetches official sources, preserves their text/footnotes and validates every expected verse. The source version check fails closed if metadata or site markup changed.
3. Review the resulting text/metadata diff and catalogue. Run the validation/tests above. Commit **all new package files and the catalogue together**, then push to `main`. Never overwrite or delete previously published package files.
4. The app checks catalogue metadata at most every 12 hours. Newly available editions appear without an app release. Existing books remain readable offline and can be updated using the update button. Availability can be disabled without deleting a user's local copy. New reader protocols/features still need an app release.

The validation workflow runs on push/PR. A scheduled upstream check reports a failed workflow if a configured source version changes; it never automatically publishes unreviewed text. Periodically rebuild with `--refresh` as well, since upstream may correct content without changing its version. Upstream failures must not be worked around with guessed, empty or differently authored text.

For a catalogue rollback, republish the reviewed previous entries with a **higher** revision; do not lower the revision or force-push history. To retire an edition, set `enabled` to false, rebuild and publish. Keep its immutable files available for existing clients.

For an app release, refresh its bundled metadata using the companion app's `scripts/quran/sync_translation_catalogue.py --repository <this-checkout>`. Source JSON/CSV caches are ignored by git.
