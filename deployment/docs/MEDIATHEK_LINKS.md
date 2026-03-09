# Mediathek links for licenses

This feature stores a PeerTube watch URL in each license and updates it automatically.

## Stored fields
- `License.mediathek_url`
- `License.mediathek_url_updated_at`

## URL format
Watch URL only:
- `https://<instance>/w/<shortUUID>`
- fallback: `https://<instance>/w/<uuid>`

## Automatic scheduling
After `/admin/austausch/exporttoserverrun/` completes:
- export report now stores `success_license_numbers` in run details,
- for each successful license number, a background task is queued,
- first lookup time is `publish_time + 5 minutes`.

`publish_time` priority:
1. `Contribution.broadcast_date`
2. planned `TagesPlan.json_plan.items[].start`

## Retry strategy
`refresh_license_mediathek_url` retries when:
- PeerTube API is temporarily unavailable,
- video is not found yet (indexing delay/unlisted period).

## Manual operations
In License admin change page:
- display clickable mediathek link,
- `Refresh URL` action,
- `Clear URL` action.

In License admin list:
- `Rescan mediathek links` page allows date range enqueue.

## One-time backfill
Run command:

```bash
python manage.py backfill_mediathek_urls --from-date 2025-01-01
```

Default behavior includes only licenses with `store_in_ok_media_library=True`.
