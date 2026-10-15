# ZIP ingestion: validated, bounded, and collision-safe

RepoPilot accepts ZIP archives for **local static inspection**. ZIP metadata,
member names and decompressed bytes are untrusted. ZIP ingestion does not
execute project scripts or treat included files as instructions.

## Processing sequence

1. Reject upload files larger than **50 MiB**.
2. Parse the ZIP central directory and preflight **every entry**, including
   directories, before reserving an output location.
3. Reject archives with more than **5,000 entries** or declared uncompressed
   contents totaling more than **200 MiB**. Reject encrypted entries and
   Unix symbolic links, sockets, device nodes and other special files.
4. Reject absolute/drive-qualified names, backslashes, traversal, empty or dot
   components, control characters, Windows-reserved characters/device names,
   overly long components and paths deeper than 32 components.
5. Reject duplicate or ambiguous paths (including Unicode NFC/casefold aliases),
   and file-versus-directory conflicts, before writing any extracted file.
6. **Atomically reserve** a new private, 12-hex repository ID directory; if
   an ID collides, try another without overwriting or deleting the existing one.
7. Decompress in bounded **64 KiB chunks**; enforce actual written bytes
   against both member metadata and the 200 MiB total, not only ZIP headers.
   Open each output in exclusive creation mode, so even an unexpected duplicate
   cannot silently overwrite a previous output.
8. On any archive error or I/O failure, remove **only the directory reserved
   by the current attempt**. A failed import never removes earlier workspaces.

These guarantees are about local ZIP ingestion and filesystem paths, **not**
about whether imported source text is safe, trustworthy or free of malware.

## Adversarial regressions

From a source checkout, run the ZIP-only and full test suites:

    PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_zip_collision_and_paths.py -v
    PYTHONPATH=backend python -m unittest discover -s backend/tests -v

The tests cover case-insensitive duplicate names; path aliases (dot components,
repeated slashes and case changes); Unix symlink entries; Windows drive/backslash
paths; file/directory conflicts; corrupt ZIP reads; data streams that exceed
declared metadata; capacity limits; and randomized ID collisions. Failures
assert that no new import remains and that preexisting import files survive.

## Limitations

- Some valid but ambiguous cross-platform archives are deliberately rejected.
  Repack those archives without duplicate paths or unsupported metadata.
- Existing imports made by old versions are **not retroactively verified**.
- Bounded decompression does not sandbox Python compression libraries or
  prevent all CPU exhaustion; scanning happens inside the local backend
  process. Further isolation is required before accepting hostile uploads
  from untrusted Internet users.
- Repository inspection skips selected paths and oversized individual source
  files, so analysis is not a complete filesystem inventory.
- RepoPilot has no public-service authentication, per-user quotas or
  multi-tenant isolation. Run it only within your trusted local boundary.

See also [GitHub clone import boundaries](github-import-security.md).
