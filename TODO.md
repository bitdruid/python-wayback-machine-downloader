# TODO

## Embedded URLs get truncated (`Url.__init__`)

`url.split("://")[1]` without `maxsplit=1` mangles query params containing `://`.

```
http://example.com/?blogger=http://other.com/page
  →  example.com/%3fblogger%3dhttp
```

Causes 161 collisions in test set (277 URLs with embedded schemes); drops to 41 with `maxsplit=1`. Fixing renames ~2.3% of files — needs regression pass.

Encoded `//` collapses on join; some URLs percent-encode identically. Separate analysis needed.

## Per-job DB isolation

Lacks a job column, forcing one DB per job. Blockers: `url_archive.url` = globally unique (should be per-job), and `Database` is a class-level singleton (blocks concurrency even with shared DB).

Trade-off: only protects against single-job corruption, `rm` is already full reset, DB lives alongside output anyway.
