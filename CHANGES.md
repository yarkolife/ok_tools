CHANGELOG
=========

2026-05-12 (Version 4.10.1)
===========================

* **rental: Group non-MSA organizations into single print form**
  * Print buttons now grouped by template: MSA separate, all others combined (org_id=0)
  * PrintFormView handles org_id=0 to exclude MSA items and use default template
  * Maximum 2 print buttons per rental regardless of how many organizations

2026-05-12 (Version 4.10.0)
===========================

* **rental: Add organization-agnostic print form system**
  * Replaced hardcoded PrintFormMSAView/PrintFormOKMQView with unified PrintFormView
  * Template selection: MSA → print_form_msa.html, all other orgs → print_form_okmq.html
  * New URL pattern `/print/<org_id>/<rental_id>/` for any organization
  * Smart print_slip redirect to first organization with items in the rental
  * Per-organization print buttons on rental detail page
  * Backward-compatible redirects for old `/print/msa/` and `/print/okmq/` URLs

2026-05-01 (Version 4.9.0)
==========================

* **rental: Optimize user selection for rental process**
  * Added prioritized initial user fetch with active rental count and limit
  * Updated user serialization to use pre-annotated rental counts
  * Unified user search endpoints to reuse serialization logic
  * Added tests for new user selection and serialization behavior

2026-04-30 (Version 4.8.0)
==========================

* **rental: Add rental request signatures and room calendar**
  * Added digital signature support for rental requests (signature fields, signing sessions)
  * Added room calendar view with day/week display and availability status
  * Added email notifications for rental request approval/rejection and return receipts
  * Added rental request admin form with signature capture
  * New models: RentalConfig with employee organizations, RentalRequest signature fields
  * New templates: sign_session, room_calendar_day, email templates for issued/returned
  * Improved rental detail, wizard, and return views with better UX

* **rental: Enhance UI and filtering**
  * Added search, filters and sorting to rental day calendar
  * Improved calendar filter layout with fixed widths
  * Added standalone search styles for calendar filters
  * Updated rental CSS with improved styling

* **planung: Update calendar weeks view**
  * Improved calendar weeks CSS and JavaScript
  * Updated admin calendar template

* **translations: Update German translations**
  * Updated translations across all modules
  * Added new translation strings for rental features

2026-04-01 (Version 4.7.0)
==========================

* **licenses: Fix Nextcloud 32 upload URL and add configurable chunked upload**
  * Fixed WebDAV upload URL format for Nextcloud 32 compatibility:
    * Changed from `/public.php/webdav/` to `/public.php/dav/files/{token}/`
  * Added configurable chunked upload for large files to improve reliability:
    * New environment variable `NEXTCLOUD_CHUNKED_UPLOAD_ENABLED` to enable/disable chunked upload (default: true)
    * New environment variable `NEXTCLOUD_CHUNKED_UPLOAD_THRESHOLD` - file size threshold in MB (default: 100)
    * New environment variable `NEXTCLOUD_CHUNK_SIZE` - chunk size in MB (default: 10)
  * Updated all deployment config templates (okmq, ok-bayern, ok-nrw) with new chunked upload settings
  * Files larger than threshold now use WebDAV chunked upload protocol (MKCOL → PUT chunks → MOVE assembly)
  * Fallback to direct upload if chunked upload fails
  * Added `X-Requested-With: XMLHttpRequest` headers for better Nextcloud compatibility

2026-03-21 (Version 4.6.0)
==========================

* **registration/licenses: Add Bundesland metadata configuration**
  * Added OrganizationConfig Bundesland selection with automatic Bundesland code generation for metadata exports.
  * Extended the license metadata API to always emit `bundesland`, `bundesland_code`, `allowExchange`, and `allowExchangeOtherStates`.

* **austausch: Normalize metadata and filter feed visibility**
  * Normalized both flat legacy and nested canonical metadata payloads for sync, API import, and admin JSON import flows.
  * Persisted exchange visibility metadata on ExchangeItem records and filtered the feed by same-state vs other-state exchange permissions.
  * Added configurable same-state channel exceptions in Austausch settings for Nextcloud channel folders such as OK Magdeburg and OK Dessau.

2026-03-19 (Version 4.5.0)
==========================

* **rental: Add configurable working hours and pick lists**
  * Added weekday opening-hour fields to rental configuration plus validation helpers for admin and public booking flows.
  * Updated rental dashboards and detail views with working-hour-aware time selection, clearer availability feedback, and printable pick-list support.
  * Added rental migrations, new working-hours tests, and per-item pick-list fields for issue preparation.

* **contributions/dashboard: Extend published metadata output**
  * Added `mediathek_url` to the program schedule API response and admin documentation examples.
  * Improved dashboard chart translation handling and empty-state copy.
  * Kept filtered planning calendar cells out of keyboard navigation while preserving layout.

2026-03-13 (Version 4.4.0)
==========================

* **austausch: Add resumable chunked upload with state tracking**
  * Implemented resumable chunked upload v2 with state file tracking for Nextcloud exchanges
  * Added PROPFIND to check already uploaded chunks on server
  * Added exponential backoff retry logic per chunk
  * Added upload state persistence to /tmp/oktools-uploads/
  * Files >50MB now use resumable chunked upload, smaller files use simple PUT
  * Fixed potential upload interruptions by saving progress state
  * Cleaned up state files and temporary upload directories on completion

2026-03-13 (Version 4.3.4)
==========================

* **austausch: Fix large file export to Nextcloud with chunked upload v2**
  * Implemented proper Nextcloud chunked upload v2 API for files >50MB.
  * Uses MKCOL to create upload directory, PUT chunks with numeric names, MOVE to assemble.
  * Fixes "Expected filesize 0 bytes" errors when uploading large video files (9GB+).
  * Added proper OC-Total-Length headers for quota checks on each chunk.
  * Uses requests.Session for connection reuse during chunked uploads.

2026-03-10 (Version 4.3.3)
==========================

* **licenses/austausch: Mediathek URL backfill and export UX improvements**
  * Added management command `backfill_mediathek_urls` to populate missing Mediathek links for existing licenses.
  * Added Mediathek-oriented admin rescan template and license admin improvements for refresh workflows.
  * Extended exchange export templates/services/tasks with improved result presentation and processing.
  * Added migration `licenses/0024_license_mediathek_url_fields.py` and related test coverage.
  * Added deployment documentation for Mediathek links.

2026-03-10 (Version 4.3.2)
==========================

* **licenses: Mediathek publication notification email**
  * Added a new `mediathek_published` notification event and email templates (subject, text, HTML).
  * Sends a user email with direct Mediathek link when `mediathek_url` is set for the first time.
  * Delivery is deduplicated via notification events to prevent duplicate sends.
  * Admin-triggered Mediathek refresh/rescan flows explicitly disable email sending.
  * Extended email render command support for `mediathek_published` preview.

2026-03-09 (Version 4.3.1)
==========================

* **licenses: Signature session cleanup command**
  * Added management command `cleanup_signing_sessions` to remove expired signature sessions.
  * Added test coverage for signature session cleanup.

* **tools: Video rendering and slideshow improvements**
  * Added duration mode to slideshow creator for fixed-duration or fit-content modes.
  * Improved video generator service with enhanced rendering options.
  * Updated templates for slideshow creator, detail view, and video render job list.
  * Added German translations for tools module.

* **registration: Legal texts and privacy policy**
  * Added legal_texts.py with GDPR and imprint content.
  * Updated privacy policy templates with improved content.
  * Added registration tests for legal text handling.

* **media_files: Video render API tests**
  * Added test coverage for video render API endpoints.

* **General: Settings and URL updates**
  * Added new settings for signature and video features.
  * Updated URL configurations.

2026-03-06 (Version 4.3.0)
==========================

* **licenses: Signature v2 and phone QR signing flow**
  * Added signature v2 fields (SVG, biometric points, metadata, method, signed timestamp) and QR signing sessions with mobile signing page and session lifecycle endpoints.
  * Updated create/update UX to use explicit signature method selection, desktop-first QR recommendation, and phone-to-canvas synchronization before submit.
  * Improved PDF signature insertion by preferring SVG/points rendering and preserving austausch compatibility via `has_any_signature()` checks.
  * Added migration and test coverage for signature session flow and payload validation.

2026-03-05 (Version 4.2.0)
==========================

* **licenses/austausch: Expand metadata API fields and import mapping**
  * Kept `name` for backward compatibility and added metadata fields (`subtitle`, `furtherPersons`, `profile`, `duration`, exchange/repetition/youth flags).
  * Extended Austausch remote metadata mapping to import subtitle, participants, tags, category, profile, and permission flags into local licenses.
  * Added test coverage for extended metadata payload and end-to-end API-based field mapping in Austausch imports.

2026-03-05 (Version 4.1.0)
==========================

* **Austausch: API-backed license identity mapping per channel**
  * Added channel-level OK-Tools API credentials and health tracking in Exchange configuration.
  * Resolved imports by stable `(source_channel, contribution_id)` mapping to prevent title-based license reuse.
  * Embedded channel API settings into `ExchangeConfig` admin and added German translations for new fields.

2026-03-02 (Version 4.0.19)
==========================

* **admin: Replace emoji icons with Feather Icons (Outline) SVGs**
  * Replaced all emoji characters (🎬⚠️✅❌🕒📝🗨️▶️🔍⏳📦📡📁📥💾🔢⏱️📊🎛️📋🔐📤📖🔄✓✗☁️📍) with professional inline Feather Icons SVGs across 22 files in 8 apps.
  * Affected: `planung`, `licenses`, `media_files`, `inventory`, `contributions`, `austausch`, `tools`, `ok_tools`.
  * Added CSS styles for SVG icon sizing and layout in `planung/static/planung/css/calendar_weeks.css`.
  * Changed `calendar_weeks.js` comment detection from emoji text matching to `data-has-comment` attribute.
  * Console/management commands and `.po` translation files are unchanged.

2026-03-02 (Version 4.0.18)
==========================

* **austausch: Fix sync ignoring videos with old modification dates**
  * Updated Nextcloud sync logic to group files first and check `lookback_date` against the latest modification date in the file group.
  * Ensures that older video files (e.g. from 2024) are imported if their associated `.meta.json` was recently generated.

2026-03-02 (Version 4.0.17)
==========================

* **austausch: Fix duration extraction from Nextcloud meta.json**
  * Added duration parsing from .meta.json files when syncing Nextcloud exchange folders.
  * Ensures that durations are correctly populated for ExchangeItems in the database.

2026-02-23 (Version 4.0.16)
==========================

* **media_files: VFR detection and source FPS helpers for FFmpeg pipeline**
  * Added `_source_fps()` helper to extract source video framerate via metadata.
  * Added `_source_is_vfr()` to detect variable frame rate streams using ffprobe r_frame_rate vs avg_frame_rate comparison.
  * Updated rendering tests to match revised preset API (`segment_duration`, `intro_overlays`, `outro_overlays`).

* **chore: gitignore .claude/ and AGENTS.md**
  * Excluded AI tooling directories and knowledge base files from version control.

2026-02-18 (Version 4.0.15)
==========================

* **Rental: dashboard date/time defaults and period handling**
  * Improved date input synchronization in rental dashboard JavaScript.
  * Added automatic default times for period selection and safer end-date correction logic.
  * Updated hint fields to date-only UX while preserving datetime values for backend submission.

* **Rental: admin approval emails now include direct staff view link**
  * Added "View" URL to both HTML and plain-text approval email templates.
  * Extended email context generation and updated German translations.
  * Added test coverage to verify staff detail link in outbound admin emails.

* **Austausch: robust status consistency after successful import retry**
  * Ensured `ExchangeItem` status fields are corrected to imported state after successful completion.
  * Prevented stale failed-state metadata from previous retries.

2026-02-12 (Version 4.0.14)
==========================

* **Bug Fix: Dashboard 500 Error - NoneType in Template Filter**
  * Fixed `TypeError: 'NoneType' object is not subscriptable` in dashboard template rendering
    * Error occurred when `user_display_name` was `None` and filter `first` was applied
    * Added `default` filter protection in `base.html` template (lines 139, 141, 143)
    * Fixed `views.py` to ensure `user_display_name` is never `None` (dashboard view and RentalDashboardView)
    * Fallback chain: username → email → "User" for guaranteed string value
  * **Files modified:**
    * `ok_tools/templates/base.html` - Added `|default:""` filter before `|first|upper`
    * `ok_tools/views.py` - Added fallback to "User" when username/email are None

2026-02-11 (Version 4.0.13)
==========================

* **Internationalization (i18n) improvements**
  * **Program Schedule API i18n**: Added localization support for API responses
    * Info block title now translatable via `_('Info block')`
    * Credits text translatable: `_('A contribution by {}').format(profile)`
    * Dynamic endpoint URL in API documentation modal
  * **API Documentation Modal i18n**: Full translation support for JavaScript UI
    * All modal strings extracted to `contributionsI18n` object
    * Uses Django template `{% trans %}` tags for translation
    * Copy button messages, labels, and descriptions translatable
  * **Middleware language detection improvement**: Enhanced `ForceDefaultLanguageMiddleware`
    * Now respects Django standard language detection (URL/cookie/Accept-Language)
    * Falls back to `LANGUAGE_CODE` only when no language detected
    * Better multi-language support for users with different browser settings
  * **New test**: Added `test_program_api_i18n.py` for i18n API testing
  * **Updated translations**: Refreshed German translations across all modules
    * ok_tools, austausch, licenses, media_files, planung, rental, tools

2026-02-10 (Version 4.0.12)
==========================

* **Contributions: Program Schedule API**
  * **New API endpoint**: Added `/contributions/api/program/` for retrieving program schedules via API
    * Token-based authentication required (similar to license metadata API)
    * Supports single date queries (`date` parameter: YYYY-MM-DD)
    * Supports date range queries (`date_from` and `date_to` parameters)
    * Optional time filtering (`start_time` and `end_time` parameters)
    * Returns formatted program data with automatic info block generation for gaps
  * **Admin integration**: Added API documentation modal in Contributions admin
    * API Documentation button in admin change list
    * Query parameters table with examples
    * cURL and JavaScript code examples
    * Copy-to-clipboard functionality for tokens and examples
    * German translations for all API documentation strings
  * **Smart info blocks**: Automatic generation and merging of info blocks
    * Info blocks automatically inserted for gaps > 1 minute between programs
    * Consecutive info blocks are merged to optimize program schedule
    * Configurable tolerance for gap detection
  * **German translations**: Added complete German translations for API documentation
    * Translations added to `ok_tools/locale/de/LC_MESSAGES/django.po`
    * Covers all UI strings, parameter descriptions, and help texts

2026-02-10 (Version 4.0.11)
==========================

* **Austausch: exported license tracking**
  * **ExportedLicense model**: New model to track exported licenses and prevent duplicate exports
  * **Migration support**: Added migration 0014_exportedlicense.py for ExportedLicense model
  * **Data migration**: Added migration 0015_migrate_exported_licenses.py to migrate existing exported licenses
  * **Export service updates**: Updated export_to_server_service to track exported licenses
  * **Views updates**: Updated views to handle exported license tracking

* **Planning module: calendar weeks UI improvements**
  * **Enhanced calendar weeks admin UI**: Improved layout, interactions, and readability
  * **CSS updates**: Better styling for calendar weeks interface
  * **JavaScript improvements**: Enhanced functionality and user interactions
  * **Template updates**: Improved calendar weeks HTML template

* **Licenses module updates**
  * **License creation template**: Updated create.html with improvements
  * **Views updates**: Enhanced license views functionality

* **Media files tasks updates**
  * **Task improvements**: Updated media_files/tasks.py with enhancements

2026-02-09 (Version 4.0.10)
===========================

* **Tools module enhancements**
  * **Dedicated render queue routing**: Routed all Celery tasks from the Tools module to the `render` queue to isolate heavy workloads
  * **Audio normalization improvements**: Added AI-based denoising with neural networks (arnndn), enhanced analysis, and intelligent recommendations
  * **Loudness normalization**: Added support for dynamic/linear mode detection and compressor linking options
  * **RNN model integration**: Automatic download and integration of RNN models for AI-based audio processing
  * **Analysis improvements**: Enhanced noise analysis with silence detection and audio characteristic analysis

* **Calendar and rental system fixes**
  * **Nextcloud calendar integration**: Fixed multiple room booking issue where separate calendar entries were created for same rental request
  * **Single event creation**: Multiple rooms booked in same time period now create single calendar event with all rooms listed
  * **Event management**: Improved handling of shared events when rooms are added/removed from rental requests

* **Translation and internationalization**
  * **Celery translation compilation**: Added translation compilation in Celery worker startup to ensure consistent language in email notifications
  * **Email localization**: Fixed issue where license notification emails fell back to English in worker processes
  * **Language consistency**: Ensured email templates render in organization's default language in Celery tasks

* **Media files and video processing**
  * **Video duplication management**: Enhanced duplicate detection and management with quality-based prioritization
  * **Storage optimization**: Improved auto-copy mechanisms and archive protection features
  * **Metadata extraction**: Enhanced video metadata extraction and processing capabilities

* **System stability and performance**
  * **Queue management**: Improved Celery task routing and worker distribution
  * **Error handling**: Enhanced error logging and debugging capabilities
  * **Process isolation**: Better separation of email rendering from web request cycle

2026-02-08 (Version 4.0.9)
==========================

* **Deployment configurations update**
  * Updated docker-compose production files with improved service configurations
  * Enhanced environment variable documentation
  * Updated deployment scripts for better reliability
  * Added new configuration templates
* **Media files module improvements**
  * Updated FFmpeg rendering utilities for video processing
  * Enhanced background task processing for media operations

2026-02-08 (Version 4.0.8)
===========================

* **Planning module (Planung): service-layer refactor and calendar UX update**
  * Introduced dedicated planning services (`plan_service`, `validation_service`, `notification_service`, `auto_copy_service`) and wired them into views/admin flows.
  * Added planning domain models and migration `0002_plantemplate_planchangelog` for reusable templates and schedule change history.
  * Reworked calendar week admin UI (template, CSS, JavaScript) with improved layout, interactions, and readability.
  * Extended planning routes/views and added tests for services and views.
  * Updated German translation catalogs for planning module and dashboard/admin texts.
* **Licenses and shared UI polish**
  * Improved license update template/view behavior and aligned shared dashboard/page/table styling.

2026-02-06 (Version 4.0.7)
===========================

* **Austausch: network share export destination**
  * Added export destination switch: Nextcloud or Network Share.
  * Added network share path settings, optional subfolder, and Windows root mapping for `files.txt` entries.
  * Implemented atomic copy/write helpers and locked append for stable concurrent export writes.
  * Extended export service and admin UI for network share workflow.
  * Added migration `0013_add_export_destination_network_share`.
  * Added tests for network share export helpers.
* **UI and translations**
  * Minor sidebar/theme/welcome template polish.
  * Updated German translation catalogs across modules.

2026-02-05 (Version 4.0.6)
===========================

* **UI refresh and accessibility**
  * Updated dashboard design system (tokens, layouts, components) and theme styling.
  * Added theme manager with toggle and dark theme updates.
  * Improved dashboard, rental, and accessibility JavaScript with i18n-safe strings.
* **Licenses: UX polish**
  * Refined license detail and edit layouts with improved status rendering.
* **Registration: branding and templates**
  * Added organization logo fields with sidebar branding support.
  * Refreshed login, registration, and profile templates.

2026-02-04 (Version 4.0.5)
===========================

* **Licenses: form UX and upload flow**
  * AJAX form submission returns JSON payload for post-create UI handling.
  * Added translated help texts and modal messages for license creation.
  * Extended create form UI and upload progress handling.
* **Tools: media library additions**
  * Add project media/audio to the library from the slideshow editor.
  * New API endpoints for library conversion with UI actions.
* **Austausch: export timezone polish**
  * Export-to-server selection uses local time for broadcast dates.
  * Export result page loads timezone template filters.
* **Database**
  * Add migration to remove UserJourney.license FK.

2026-02-04 (Version 4.0.4)
===========================

* **Tools: slideshow output & storage path handling**
  * Stream generated slideshows with HTTP Range support for reliable playback.
  * Resolve media/audio/output paths using ToolsConfig storage/output paths with safe fallbacks.
  * Cleanup task now deletes media/audio/output files using resolved paths.
* **Austausch: export & WebDAV fixes**
  * Export result timestamps render in local time.
  * Export-to-server selection list uses local time for broadcast dates.
  * Export result page loads with timezone template filters enabled.
  * Expiring upload shares use local date with safer minimum validity.
  * WebDAV URL resolution uses storage-aware base path.
  * License export skips numbers already successfully exported across runs.
* **Licenses: deletion safety**
  * Clear UserJourney links before deleting confirmed licenses.
* **Project hygiene**
  * Ignore local plans/ folder in Git.

2026-01-28 (Version 4.0.3)
===========================

* **Austausch: Export to server**
  * **Export to server workflow**: Upload video, PDF, JSON (and optional thumbnails) to Nextcloud WebDAV
    * Step 1: Choose mode (by contributions or by license numbers)
    * Step 2: Select contributions/licenses and start export
    * Result page: success/failure/skipped counts and details
  * **ExchangeConfig**: New export settings
    * `upload_server_path`: WebDAV path for upload (distinct from download/sync paths)
    * `default_media_authority`: Optional preselected "Offener Kanal" for export
    * `local_pdf_fallback_path`, `local_pdf_fallback_path_2`: Local directories for unsigned license PDFs ({number}_*.pdf)
    * `upload_thumbnail_enabled`, `thumbnail_storage_path`: Optional cover/thumbnail upload
  * **ExportToServerRun**: Model for export run results (read-only in Admin)
  * **Celery task**: `export_to_server_task` runs upload in background; Nextcloud service extended for upload
  * **Contributions/Licenses**: Admin actions and serializers extended for export selection

2026-01-26 (Version 4.0.2)
===========================

* **Audio Normalization: AI-based denoising and enhanced analysis**
  * **Neural Network Denoising (arnndn)**: Added support for AI-based audio denoising using RNN models
    * New AI presets: `tv_ai_speech`, `tv_ai_strong`, `web_ai_speech` for better speech clarity
    * Automatic RNN model download during installation/update from public repositories
    * Models stored in `tools/rnn_models/` directory (std.rnnn, lq.rnnn)
    * Fallback to FFT-based denoising (afftdn) if RNN models unavailable
    * Configurable model path via `ToolsConfig.arnndn_model_path` or `TOOLS_ARNNDN_MODEL_PATH`
  * **Enhanced Audio Filters**: Added support for additional FFmpeg filters
    * `lowpass` filter for high-frequency noise removal (10-14 kHz)
    * `dialoguenhance` filter for speech clarity improvement in stereo (FFmpeg 5+)
    * Improved filter chain building with automatic model detection
  * **Noise Analysis**: Automatic noise detection and analysis
    * Uses `silencedetect` and `astats` filters to analyze audio characteristics
    * Detects background noise level, silence ratio, peak levels
    * Noise analysis data stored in job metadata for recommendations
    * Displayed in UI with detailed metrics (silence ratio, noise level, peak/mean levels)
  * **Intelligent Recommendations**: Enhanced recommendation system based on audio analysis
    * AI presets recommended when high background noise detected (> -40 dB)
    * Strong AI preset recommended for very high noise (> -35 dB) or continuous noise
    * Recommendations adapt to target (TV vs Web) and model availability
    * Suggestions include specific reasons (noise level, dynamics, peak levels)
  * **Automatic Model Installation**: RNN models downloaded automatically
    * Script `tools/rnn_models/download_models.sh` downloads models during install/update
    * Integrated into `install.sh`, `update.sh`, and `entrypoint.production.sh`
    * Models downloaded from GitHub repositories (GregorR/rnnoise-models)
    * Non-critical: system continues if download fails (manual download possible)
  * **Default Model Path**: Automatic detection of default model location
    * System automatically uses `tools/rnn_models/std.rnnn` if available
    * No manual configuration required if models are in default location
    * Override via config or environment variable if needed

2026-01-23 (Version 4.0.1)
==========================

* **Licenses: status email targeting and user-upload chain**
  * **LicensesConfig**
    * New `notification_media_authority_names`: send status emails only to users whose
      Profile belongs to selected Media Authorities (Offene Kanäle/Bürgermedien).
      Empty = send to all. Configure in Admin → Licenses → Licenses configuration.
  * **NextcloudVideoFile**
    * New `user_uploaded`: True when the rightsholder uploads via the portal; False
      when staff creates the record (e.g. in Admin). Shown in Admin.
  * **Email chain (draft_scheduled, planned_scheduled, contributions_available)**
    * Sent only if the license has a **user-uploaded** Nextcloud video
      (`user_uploaded=True`). Archive-only or staff-linked videos no longer trigger
      these three emails.
  * **video_uploaded** still sent for any new NextcloudVideoFile; all four types
    are filtered by `notification_media_authority_names` when set.

2026-01-20 (Version 4.0.0)
==========================

* **Major Release: Config & Tools Consolidation**
  * **New app: Tools**
    * **Video slideshow creator** (models, views, templates) with async generation via Celery
    * **Video render jobs** (models, views, templates) + rendering pipeline utilities
    * **Preset management UI** in Django admin (preset editor + VideoPreset admin pages)
    * **Audio normalize jobs** (models, services, presets JSON, waveform generation) + Celery tasks
    * **New Tools API endpoints** (project/job CRUD and status endpoints)
  * **DB-backed module configuration (with env fallbacks)**
    * **Registration**: `RegistrationConfig` + `OrganizationConfig` (+ migrations)
    * **Rental**: `RentalConfig` (+ migration) and centralized config helpers
    * **Licenses**: `LicensesConfig` (+ migrations) incl. download path + email toggles
    * **Media Files**: `MediaFilesConfig` (+ migrations) incl. supported formats + HEVC transcode toggle
    * **Tools**: Tools config model added as part of new app
    * **Migration helper command**: `migrate_module_configs` (fills DB config from env for empty/default values)
  * **Licenses: workflow notifications & automation**
    * **License notification event model** + Celery tasks for scheduled status emails
    * **Email templates** added (draft/planned scheduled, video uploaded, contributions available)
    * Updates to serializers/services/views for Nextcloud + notification flow
  * **Media Files refactor**
    * **Video presets moved out of `media_files` into Tools presets infrastructure** (+ migration)
    * Admin/commands/tasks cleanup and maintenance improvements
    * Added admin confirmation template for force-deleting protected archive entries
  * **Dashboard & analytics**
    * Cache invalidation and signal handling updates
    * Widget improvements (inventory/projects/funnel) + dashboard base template update
  * **Deployment & operations**
    * Updated `.env` templates with new module flags/settings (Tools, configs, tasks)
    * Entrypoint/update scripts run config migration step (`migrate_module_configs`)
  * **Translations**
    * Updated German `.po` files across modules and added Tools translations

2026-01-15 (Version 3.3.1)
===========================

* **Tools Module: Media Library**
  * **Media Library**: Reusable media files across multiple projects
    * Upload images and videos to shared library
    * Browse library by media type (images/videos)
    * Add library media to any project without re-uploading
    * Staff-only access to library management
    * Separate API endpoints for library operations
  * **Bug Fixes**
    * Fixed black background for padded media (was green)

2026-01-15 (Version 3.3.0)
===========================

* **New Module: Tools**
  * **Video Slideshow Generator**: Create video slideshows from images and videos
    * Drag & drop interface for media upload
    * Audio background music selection
    * Configurable transitions (fade, wipe, slide, etc.)
    * Adjustable duration and quality settings
    * Preview and download capabilities
    * Async generation via Celery
  * Module can be enabled/disabled via `TOOLS_ENABLED` environment variable
  * Storage paths configurable via `TOOLS_STORAGE_PATH` and `TOOLS_OUTPUT_PATH`
  * Automatic cleanup of old projects via Celery Beat

2026-01-14 (Version 3.2.12)
===========================

* **Rental System Updates**
  * **Email confirmations** now include booking details and HTML versions
  * **User-friendly booking links** via `RENTAL_REQUEST_URL_TEMPLATE`
  * **User detail page** at `/rental/user/rental/<id>/` with request summary
  * **Admin confirmation action** for draft requests in rental detail view
  * **User/Admin request visibility** improvements in dashboards
  * **Deployment templates** updated with `RENTAL_REQUEST_URL_TEMPLATE`

2026-01-12 (Version 3.2.11)
===========================

* **Planning Module (Planung) Enhancements**
  * **Manual Time Setting Improvements**: Enhanced manual time setting with overlap protection
    * Strict mode: Manual time settings are preserved and not auto-adjusted
    * Added overlap validation to prevent videos from overlapping when manually positioned
    * Videos cannot start before the previous video ends (even in manual mode)
    * Visual indicator (light blue background) for manually set times
  * **Multi-Day Video Support**: Added support for videos extending beyond midnight
    * End times now display day offset when video extends to next day (e.g., "02:00:00 (+1 day)")
    * Day offset shown in small gray text below the time (similar to seconds display)
    * Proper handling of videos longer than the broadcast block
    * Correct time calculation across day boundaries
  * **German Translations**: Added German translations for new messages
    * "day" → "Tag"
    * Overlap warning messages in German

2026-01-07 (Version 3.2.10)
===========================

* **Admin Interface Improvements**
  * **SVG Icons Replacement**: Replaced Unicode triangle characters with SVG icons for better rendering
    * Admin sidebar and index page now use SVG triangle icons instead of Unicode characters
    * SVG icons provide consistent rendering across all platforms and browsers
    * No dependency on font support for special Unicode characters
    * Better visual quality with crisp rendering at any size
    * Proper white color (#ffffff) with !important flags to prevent theme overrides
    * Removed all font-family, font-style, and font-weight dependencies
    * Clean SVG implementation with proper path styling
  * **Play Icon SVG**: Replaced Unicode play character with SVG icon in exchange feed
    * Exchange feed video previews now use SVG play icon instead of Unicode character
    * Better visual quality with drop-shadow effect
    * Consistent rendering across all platforms
    * Proper sizing (128x128px) with responsive display

* **Content Exchange Module Enhancements**
  * **Filename Normalization**: Added comprehensive filename normalization for exchange imports
    * German umlaut support: ü->ue, ä->ae, ö->oe, ß->ss
    * Normalize non-ASCII characters using Unicode decomposition
    * Sanitize filenames for filesystem compatibility
    * Remove or replace invalid filesystem characters
    * Remove multiple consecutive underscores
  * **Error Handling Improvements**: Enhanced error handling in ExchangeImport admin
    * Added error message display in ExchangeImport admin list
    * Error messages truncated to 100 characters with full message in tooltip
    * Red color styling for error visibility
  * **Statistics Improvements**: Improved exchange feed statistics
    * Statistics now only count video items (matching queryset filter)
    * Added failed items counter to exchange feed statistics
    * Failed count displayed with red color for visibility
  * **Play Icon Rendering**: Improved play icon rendering in exchange feed template
    * Added !important flag to play icon color for better visibility
    * Added explicit font family stack for Unicode triangle character
    * Included monospace fallback for consistent rendering
    * Added font-style and font-weight normalization
    * Improved cross-platform compatibility

* **Admin Interface Fixes**
  * **Icon Color Fix**: Fixed icon color in admin sidebar and index page
    * Replaced CSS variable with explicit white color (#fff) for better compatibility
    * Ensures icons are always visible regardless of theme settings
    * Applied !important flag to prevent theme overrides

2026-01-07 (Version 3.2.9)
==========================

* **Content Exchange Module Enhancements**
  * **Automatic Thumbnail Generation**: Added automatic thumbnail generation for exchange videos
    * Thumbnails are generated on-demand from video files via HTTP URL (WebDAV)
    * Supports both standard WebDAV and GroupFolders paths
    * Thumbnails are cached locally to avoid repeated generation
    * Fallback mechanism: direct HTTP input, then range download if first method fails
    * Integration with exchange feed view for visual preview
  * **HTTP Thumbnail Generation**: New utility functions for generating thumbnails from HTTP URLs
    * `generate_thumbnail_from_http_url()` - Direct HTTP input with seeking support
    * `generate_thumbnail_from_http_range()` - Range request fallback for compatibility
    * Both methods support HTTP authentication (username:password@host format)
    * Configurable timeout (60 seconds for HTTP URLs vs 10 seconds for local files)
    * Efficient seeking without downloading entire video file
  * **WebDAV URL Resolution**: Improved WebDAV URL handling for different Nextcloud storage types
    * New `get_webdav_url_for_path()` method to determine correct WebDAV base URL
    * Automatic detection of GroupFolders vs standard WebDAV paths
    * Proper URL encoding for special characters in file paths
  * **Template Improvements**: Enhanced exchange feed template for better thumbnail display
    * Improved error handling for missing thumbnails
    * Graceful fallback to play icon if thumbnail generation fails
    * Better visual feedback with onload/onerror handlers

* **Media Files Utils Enhancements**
  * **HTTP URL Support**: Extended `generate_thumbnail()` function to support HTTP/HTTPS URLs
    * Automatically detects HTTP URLs and increases timeout accordingly
    * Works with WebDAV endpoints for remote video file processing
    * Supports both local file paths and HTTP URLs seamlessly

2026-01-07 (Version 3.2.8)
==========================

* **Content Exchange Module (Austausch)**
  * **New Module for Content Exchange**: Added comprehensive content exchange module for sharing content between channels
    * Nextcloud folder synchronization for automatic content discovery
    * Exchange item tracking with video files, PDFs, and thumbnails
    * Contribution ID extraction from filenames for OK-Tools managed content
    * Exchange feed view accessible to staff members via admin interface
    * Configurable sync schedule via Celery Beat (default: daily at 2:00 AM)
    * Support for multiple exchange folders and channel identification
    * Optional module - enabled via `AUSTAUSCH_ENABLED` environment variable
  * **Configuration Templates Updated**: Added Austausch configuration to all deployment templates
    * Added `AUSTAUSCH_ENABLED` setting to ok-bayern, ok-nrw, and okmq templates
    * Added `CELERY_BEAT_SYNC_EXCHANGE` cron schedule configuration
    * Default: disabled for backward compatibility
  * **Admin Integration**: Exchange Feed link added to admin sidebar when module is enabled
    * Accessible via Austausch → Exchange Feed in admin menu
    * Staff-only access with login requirement
    * Paginated list view with filtering and search capabilities
  * **Celery Task Integration**: New periodic task `sync_exchange_folders` for automated synchronization
    * Runs automatically when module is enabled and Celery Beat is configured
    * Integrated with `setup_periodic_tasks` management command
    * Configurable schedule via environment variable

* **Media Files Migration**
  * **Database Schema Update**: Added verbose name to VideoFile.created_at field
    * Migration 0015_alter_videofile_created_at.py
    * Improves admin interface display consistency

2026-01-05 (Version 3.2.7)
==========================

* **Bug Fix: Video Deletion Error**
  * **Fixed UnboundLocalError in VideoFile bulk deletion**: Resolved 500 error when deleting videos through admin interface
    * Removed duplicate local import of translation function `_` that caused scope issue
    * Translation function now correctly uses module-level import throughout the method
    * Bulk deletion of videos now works without Internal Server Error

2026-01-02 (Version 3.2.6)
==========================

* **Celery Integration for System Management Commands**
  * **All System Management Commands Now Run via Celery**: Migrated all management commands to asynchronous execution
    * System Management page commands now execute via Celery tasks instead of blocking web requests
    * Commands include: scan_video_storage, auto_scan, sync_licenses_videos, link_orphan_licenses, cleanup_playout, find_duplicates, cleanup_duplicates
    * Tasks run in background, allowing users to continue working while commands execute
    * Improved scalability - can distribute workload across multiple Celery workers
  * **Storage Location Scanning via Celery**: Scan button and bulk scan actions now use Celery
    * Individual storage scan button (🔍 Scan) now queues Celery task instead of blocking
    * Bulk "Scan selected storage locations" action queues tasks for all selected storages
    * All scan operations execute asynchronously in background
    * Users receive Task ID and link to monitor progress via Celery Results admin
  * **Enhanced User Feedback**: Improved task status tracking and user notifications
    * Task ID displayed after queuing commands
    * Direct links to Celery Results admin page for monitoring task progress
    * Better error handling and user messaging for task queueing
    * All task executions are logged with user information for audit trail

2026-01-02 (Version 3.2.5)
==========================

* **Performance Optimization: Checksum Verification**
  * **Size-Only Verification for ARCHIVE Sources**: Major performance improvement for copying from archive
    * Uses file size comparison instead of checksum calculation for ARCHIVE sources
    * No checksum calculation at all - only compares file sizes before and after copy
    * Verification takes milliseconds instead of minutes (8-9 minutes saved per 6-7 GB file)
    * Archive files are already verified, so size comparison is sufficient for integrity check
    * Significantly reduces copy time: from ~11 minutes to ~2.5-3 minutes for large files
  * **Optimized Checksum Calculation During Copy**: Checksum calculated during file copy, not after
    * Destination checksum is calculated chunk-by-chunk during copy operation
    * Avoids reading file twice (source checksum + copy + destination checksum)
    * Uses 8 MB chunks for better performance
    * Applies to CUSTOM sources (ARCHIVE uses size-only verification)
  * **Configurable Checksum Verification**: Added settings to control checksum verification
    * `VIDEO_COPY_VERIFY_CHECKSUM`: Enable/disable checksum verification (default: true)
    * `VIDEO_COPY_USE_MD5_FOR_ARCHIVE`: Use faster MD5 for ARCHIVE sources (default: true, but ARCHIVE now uses size-only)
    * Allows fine-tuning between security and performance
  * **Improved Logging for Checksum Operations**: Enhanced logging to track verification method
    * Added INFO-level logging to show verification method (size-only vs checksum)
    * Logs file copy progress and verification steps for better debugging
    * Helps monitor performance improvements and verify correct verification method

2026-01-02 (Version 3.2.4)
==========================

* **Bug Fix: Video Deletion from CUSTOM Storage**
  * **Fixed Database Error**: Resolved error when deleting VideoFile records from CUSTOM storage after successful copy
    * Fixed `ValueError: save() prohibited to prevent data loss due to unsaved related object 'video_file'`
    * FileOperation records are now saved before deleting VideoFile to prevent database errors
    * Operation status is updated and saved before VideoFile deletion
    * Improved error handling for cases when source file is missing
    * All database records are now properly updated during deletion operations

2026-01-02 (Version 3.2.3)
==========================

* **Video Storage Automation Enhancements**
  * **Default Playout Storage Selection**: Added intelligent selection of default playout storage for main broadcasts
    * Configurable via `VIDEO_DEFAULT_PLAYOUT_STORAGE_NAME` or `VIDEO_DEFAULT_PLAYOUT_STORAGE_PATH`
    * Auto-detects storage containing "000_Sendungen" in path or "Sendungen" in name
    * Falls back to first available PLAYOUT storage if nothing matches
    * Ensures videos are copied to correct playout location (main broadcasts vs. previews/trailers)
  * **Automatic Deletion from CUSTOM Storage**: Added automatic cleanup of CUSTOM storage after successful copy
    * Videos are moved (deleted from CUSTOM) after successful copy to archive and playout
    * Only deletes if source was CUSTOM and all required copies succeeded
    * Prevents duplicate records and keeps CUSTOM storage (entry point) clean
    * Configurable via `VIDEO_AUTO_DELETE_FROM_CUSTOM` setting (default: true)
    * Creates FileOperation records for deletion tracking
    * Updates all database records properly during copy and delete operations
  * **Enhanced Database Record Management**: Improved database record updates during video operations
    * All metadata is copied when creating new VideoFile records
    * FileOperation records are properly linked to new video records
    * Deletion operations are fully tracked in FileOperation table
    * Better logging for all database operations

2026-01-02 (Version 3.2.2)
==========================

* **Video Storage Automation and Archive Protection**
  * **Automatic Video Copying During Planning**: Added automatic video file copying when saving broadcast plans
    * Videos are automatically copied to archive and playout storage when plan is saved (not draft)
    * Smart source selection: prefers CUSTOM storage if file is recent (within configured days), otherwise uses ARCHIVE
    * Supports weekly folder organization (YYYY_KW_WW format) in playout storage
    * Configurable via environment variables for different installation types
    * Comprehensive logging and error handling
  * **Archive Storage Protection**: Added protection against accidental deletion of archive videos
    * Videos in ARCHIVE storage can be read and copied, but deletion is disabled in admin interface
    * Protection can be enabled/disabled via `VIDEO_ARCHIVE_PROTECTED` setting
    * Works for both single and bulk deletion operations
    * Prevents data loss while allowing read and copy operations
  * **Smart Source Selection**: Intelligent video source selection for copying operations
    * Prefers CUSTOM storage if file was updated within configured days (default: 7 days)
    * Falls back to ARCHIVE storage for older files
    * Excludes PLAYOUT storage from source selection to avoid circular copying
    * Configurable via `VIDEO_SOURCE_PREFERENCE_CUSTOM_DAYS` setting
  * **Configuration via Environment Variables**: Added 6 new settings for flexible configuration
    * `VIDEO_AUTO_COPY_ON_SCHEDULE`: Enable automatic copying when saving plans
    * `VIDEO_AUTO_COPY_TO_ARCHIVE`: Copy videos to archive storage automatically
    * `VIDEO_AUTO_COPY_TO_PLAYOUT`: Copy videos to playout storage automatically
    * `VIDEO_USE_WEEKLY_FOLDERS`: Use weekly folders (YYYY_KW_WW) in playout storage
    * `VIDEO_ARCHIVE_PROTECTED`: Protect archive from deletion (default: true)
    * `VIDEO_SOURCE_PREFERENCE_CUSTOM_DAYS`: Days to consider CUSTOM files as recent (default: 7)
    * All settings default to safe values (disabled) for backward compatibility
  * **Celery Task Integration**: New Celery task `copy_videos_for_plan` for asynchronous video copying
    * Runs automatically when plan is saved (if enabled)
    * Can run synchronously if Celery is not available
    * Returns detailed results for user notifications
    * Handles errors gracefully with comprehensive logging
  * **Documentation Updates**: Added comprehensive documentation for new features
    * New section in ENV_VARIABLES.md for video storage automation configuration
    * Examples for different installation types (with/without archive)
    * Configuration examples for full automation vs. disabled mode

2026-01-02 (Version 3.2.1)
==========================

* **Celery Configuration Improvements**
  * **Configurable Task Time Limits**: Added support for configuring Celery task time limits via environment variables
    * `CELERY_TASK_TIME_LIMIT` and `CELERY_TASK_SOFT_TIME_LIMIT` can now be set in `.env` files
    * Default values remain 30 minutes (hard limit) and 25 minutes (soft limit)
    * Recommended values for large video rendering: 60-120 minutes
    * Updated all configuration templates (okmq, ok-nrw, ok-bayern) with recommended values
  * **Video Rendering**: Fixed timeout issues for long video rendering tasks by making time limits configurable

2026-01-02 (Version 3.2)
========================

* **Documentation Enhancements**
  * **Comprehensive README Update**: Significantly expanded README.rst with detailed module descriptions
    * Added detailed feature descriptions for all core applications (User Registration, License Management, Media Files, Planning Tools, Contributions, Projects, Inventory, Rental, Dashboard)
    * Documented all management commands organized by module (Media Files, Rental, Inventory, Licenses, Contributions, Registration, Dashboard)
    * Added comprehensive data import documentation (DISA, Inventory, Inspections) with format support and batch processing details
    * Documented service layer architecture (Inventory, Rental, Statistics, Notification, User services)
    * Added technical details about caching strategies, database optimization, and API performance
    * Enhanced feature descriptions with sub-features and capabilities for each module
  * **Module Documentation**: Complete feature breakdown for each application
    * User Registration: Email-based authentication, GDPR compliance, profile management, print registration forms
    * License Management: Nextcloud integration, video upload, metadata export, planning system integration
    * Media Files: Multiple storage locations, video rendering with presets, checksum calculation, automatic scanning
    * Planning Tools: Daily broadcast plans (TagesPlan), calendar weeks, time extraction, JSON-based storage
    * Contributions: DISA import (XLSX/XLS), primary/repetition detection, statistics, grouped display
    * Projects: ICS export, categories, target groups, demographics, project leaders
    * Inventory: Hierarchical locations, batch imports (500 items), inspection import, audit logging
    * Rental: Equipment sets, room rentals, transactions, API endpoints, availability checking
    * Dashboard: Multiple widgets, funnel metrics, alert system, real-time updates

* **Management Commands Documentation**
  * Documented all available management commands organized by module:
    * **Media Files**: auto_scan, scan_video_storage, update_video_metadata, link_orphan_licenses, sync_licenses_videos, copy_to_playout, cleanup_playout, cleanup_missing_files, cleanup_old_file_operations, find_duplicates, cleanup_duplicates
    * **Rental**: expire_room_rentals, fix_quantity_issued, fix_missing_issue_transactions, test_nextcloud_calendar
    * **Inventory**: import_inspections, link_inspections, import_locations
    * **Licenses**: import_licenses_from_wp, delete_imported_licenses, cleanup_deleted_nextcloud_videos
    * **Contributions**: export_mediathek_report
    * **Registration**: setup_organizations
    * **Dashboard**: check_alerts
  * Noted that many commands can be run from admin interface via System Management page (requires staff access)

* **Data Import Documentation**
  * **DISA Import**: Documented Excel import (XLSX/XLS) with automatic format conversion, date-based filtering, batch processing, AJAX date extraction, and validation
  * **Inventory Import**: Documented Excel import with batch processing (500 items per batch), automatic entity creation (manufacturers, categories, locations, organizations), inventory number validation (OK-XXXX format), location hierarchy creation, error logging, and status tracking
  * **Inspection Import**: Documented CSV/XLSX import with automatic date parsing from various formats, linking to inventory items by inspection number, batch processing, and error handling

* **Technical Architecture Documentation**
  * **Service Layer**: Documented service layer architecture with Inventory, Rental, Statistics, Notification, and User services for better testability and maintainability
  * **Caching Strategy**: Documented Redis-based caching with pattern-based cache key management, cache invalidation on data changes via signals, and cache versioning support
  * **Database Optimization**: Documented batch processing for imports, optimized contribution primary/repetition detection, query optimization with select_related and prefetch_related, composite indexes, and pagination with preserved prefetch relationships
  * **API Documentation**: Enhanced REST API documentation with pagination support (default 20 items, configurable up to 200), search and filtering capabilities, and ordering support

* **Additional Features Documentation**
  * **Video Rendering**: Documented preset management (database and JSON-based), customizable intro/outro overlays, text and image overlay support, animation effects (fade, slide, zoom), position presets, template-based rendering, and preview functionality
  * **Storage Management**: Documented multiple storage location support with hierarchical tracking, UNC path support for Windows networks, automatic file scanning with scheduling, storage type classification (Archive, Playout, Custom), and file availability tracking
  * **Equipment Sets**: Documented equipment set templates, quick rental setup with equipment sets, member-created equipment sets, and template-based equipment selection
  * **Alert System**: Documented configurable alert thresholds, multiple metric types (conversion rate, absolute count, trend change), alert logging and resolution tracking, notification recipients configuration, and active/inactive threshold management

2026-01-02 (Version 3.2.0)
===========================

* **Bug Fixes and Data Integrity**
  * **Rental Quantity Fix**: Fixed critical double increment bug in `quantity_issued` calculation
    * Resolved issue where `quantity_issued` was incremented twice (once in `create_transaction()` method and once in signal handler)
    * Added management commands `fix_quantity_issued` and `fix_missing_issue_transactions` for data correction
    * Commands support dry-run mode for safe testing before applying fixes
    * Full documentation added in `deployment/docs/FIX_QUANTITY_ISSUED.md`
  * **Transaction Integrity**: Ensured all rental transactions are properly tracked and synchronized
  * **Data Migration Tools**: Added tools to fix existing data affected by the bug

* **License Management Enhancements**
  * **License Cleanup Tools**: Added management command `delete_imported_licenses` for bulk deletion of imported licenses
    * Supports deletion by date range, license number range, or profile ID
    * Includes dry-run mode for safe testing
    * Automatically handles related contributions deletion
  * **Nextcloud Integration**: Added `cleanup_deleted_nextcloud_videos` command for managing deleted videos
    * Checks Nextcloud for deleted videos and marks them as deleted in database
    * Supports configurable grace period before permanent deletion
    * Integrated as periodic Celery task for automated cleanup

* **Periodic Tasks Management**
  * **Task Setup Command**: Added `setup_periodic_tasks` management command for initializing Celery Beat tasks
    * Migrates tasks from `CELERY_BEAT_SCHEDULE` to django-celery-beat database scheduler
    * Makes tasks visible and manageable via Django admin interface
    * Supports update mode for modifying existing tasks
  * **New Periodic Tasks**: Added automated cleanup tasks
    * `cleanup_deleted_nextcloud_videos`: Periodic cleanup of deleted Nextcloud videos
    * All tasks configurable via environment variables with sensible defaults

* **Database Backup Improvements**
  * **Backup Command**: Enhanced `backup_db` management command
    * Supports compression (gzip) for space-efficient backups
    * Configurable output directory
    * Automatic backup rotation via `cleanup_old_backups` task
    * Integrated as periodic Celery task (runs daily by default)

* **Version Updates**
  * **Django**: Updated to 5.2.7 (from 5.2.5)

2025-10-25 (Version 3)
========================

* **Major Architecture Improvements**
  * **Event-Driven Architecture**: Implemented asynchronous communication between rental and inventory modules using Celery events
  * **Service Layer Pattern**: Introduced service layers for inventory and rental operations with abstract interfaces for better decoupling
  * **Microservices Preparation**: Created abstract inventory service interface to prepare for future microservices transition
  **Comprehensive Architecture Documentation**: Added complete C4 model diagrams and architectural overview in `overview.md`

* **Asynchronous Task Processing**
  * **Celery Integration**: Integrated Celery with Redis for background task processing
  * **Async Inventory Import**: Implemented asynchronous inventory import with progress tracking and error handling
  * **Background Processing**: Added Celery workers for long-running operations like imports and exports

* **API Enhancements**
  * **OpenAPI/Swagger Documentation**: Added automatic API documentation with drf-spectacular
  * **REST API for Inventory**: Implemented comprehensive REST API endpoints for inventory management
  * **Token Authentication**: Enhanced API security with token-based authentication and management interface
  * **API Rate Limiting**: Added throttling protection with 100/hour for anonymous and 1000/hour for authenticated users

* **Monitoring and Observability**
  * **Prometheus Integration**: Added comprehensive metrics collection with django-prometheus
  * **JSON Logging**: Implemented structured JSON logging for improved debugging and monitoring
  * **System Metrics**: Added metrics for HTTP requests, database operations, and model operations
  * **Performance Monitoring**: Enhanced dashboard with real-time system statistics

* **Security Enhancements**
  * **Security Headers**: Implemented comprehensive security headers (HSTS, XSS protection, etc.)
  * **CSRF Protection**: Enhanced CSRF protection with secure cookie settings
  * **Clickjacking Protection**: Added X-Frame-Options headers to prevent clickjacking attacks
 * **Vulnerability Scanning**: Integrated pip-audit for automatic dependency vulnerability scanning

* **Code Quality and Type Safety**
  * **Static Type Checking**: Added comprehensive type hints with mypy integration
  * **Code Documentation**: Added Google-style docstrings for all public APIs
  * **Unit Test Coverage**: Added 100+ unit tests for service layers with 70%+ coverage
  * **Code Quality Tools**: Integrated pre-commit hooks and automated code quality checks

* **Performance Optimizations**
  * **Bulk Import Optimization**: Optimized inventory import with bulk_create/bulk_update operations (80% faster)
  * **DISA Import Efficiency**: Improved DISA import performance with reduced database queries (~95% faster)
  * **Database Query Optimization**: Continued optimization of N+1 queries across the application
  * **Cache Improvements**: Enhanced caching strategies for better performance

* **Infrastructure Improvements**
  * **Backup Management**: Added custom management command for PostgreSQL database backups
 * **Configuration Management**: Enhanced .cfg file support for comprehensive Django configuration
  * **Deployment Scripts**: Fixed and improved deployment scripts for production environments
  * **CI/CD Integration**: Enhanced CI pipeline with code coverage and vulnerability scanning

* **Bug Fixes and Stability**
  * **Admin Interface Fixes**: Resolved CSS and display issues in Django admin interface
  * **Error Handling**: Fixed KeyError and AttributeError issues in various components
  * **Import Error Resolution**: Fixed inventory and contribution import error handling
 * **Video Player Fix**: Resolved translation-related errors in video file player

2025-10-11 (Version 2.5)
========================

* **Media Files Management Module**
  * New comprehensive module for video file management
  * Automatic file discovery and metadata extraction via ffprobe
  * Support for multiple storage locations (Archive, Playout, Custom)
  * **Auto-sync duration**: License duration automatically syncs from linked video file
    * Visual warning when durations mismatch
    * One-click sync button in admin interface
    * Automatic sync via signals when video is created/updated
  * **Video player improvements**: Fixed streaming and playback issues
    * Correct MIME-type mapping for all video formats
    * Proper range request support for seeking
    * FileResponse for efficient streaming
    * Inline content disposition (no download prompts)
 * **Duration and Tags formatting**: Improved display in admin interface
    * License duration rounded to seconds (hh:mm:ss format)
    * Tags displayed without JSON brackets and quotes
    * Empty tags show as dash (-) instead of [] or null
  * **Duration mismatch tolerance**: Smart duration comparison
    * Warning only shown if difference >= 1 second
    * Prevents false alerts for sub-second differences (e.g., 0.568s)
    * Auto-sync respects same tolerance threshold
 * **Duplicate Video Management**: Comprehensive duplicate detection and management
    * **Automatic detection**: Finds videos with same number in different storage locations
    * **Quality-based prioritization**: ARCHIVE > PLAYOUT > CUSTOM, then by bitrate/resolution
    * **Checksum verification**: Identifies identical vs different files with same number
    * **Prevention system**: Blocks copying identical files to archive storage
    * **Admin interface enhancements**:
      * Visual duplicate indicators in list view (✓ PRIMARY, ⚠️ DUPLICATE)
      * Filter by duplicate status and version type
      * Bulk actions: mark as primary, delete duplicates
      * Detailed duplicate information in change forms
      * Links between all versions of same video
      * **Management command**: `find_duplicates` with JSON output and filtering options
      * **Auto-copy improvements**: Automatically selects best quality version when copying
      * **Configuration**: New settings for storage priority and duplicate prevention
      * **Documentation**: Complete guides (DUPLICATE_MANAGEMENT.md, DUPLICATE_QUICKSTART.md)
    * **Weekly Folder Organization**: Automatic weekly folder structure for playout storage
      * **Auto-detection**: Automatically determines week from planning date (ISO 8601)
      * **Folder format**: Creates folders like `2025_KW_41` for week 41 of 2025
      * **Auto-copy integration**: Videos copied to correct weekly folder when planning saved
      * **Manual copy support**: Admin copy actions also use weekly folders
      * **Automatic creation**: Creates weekly folders if they don't exist
      * **Database integration**: VideoFile.file_path includes weekly folder path
      * **Backward compatibility**: Existing videos without weekly folders still work
      * **Documentation**: Complete guide (WEEKLY_FOLDERS.md)
    * **Advanced Automation Features**: Comprehensive automation for video file management
      * **Bidirectional sync**: Automatic linking between VideoFile and License (both directions)
      * **Mass synchronization**: `sync_licenses_videos` command for bulk linking and duration sync
      * **Automatic playout cleanup**: Move videos from playout to archive when no longer in use
      * **File attribute monitoring**: Detect when files are in use via system attributes (Windows/Linux)
      * **File lock detection**: Check if files are locked by other processes using `lsof`
      * **Auto-scan integration**: `auto_scan` command for automated storage scanning
      * **Admin actions**: "Move to archive storage" bulk action with safety checks
      * **Cron integration**: Ready for automated daily/weekly maintenance tasks
      * **Comprehensive logging**: All operations tracked in FileOperation model
      * **Admin UI improvements**:
        * **Scan button**: One-click storage scanning from admin interface
        * **Search for videos**: Button to find videos for licenses without files
        * **Bulk search**: Admin action to search videos for multiple licenses
        * **Orphan license finder**: `link_orphan_licenses` command to auto-link videos
        * **System Management**: Centralized page to run all commands from admin UI
          * Auto scan, manual scan, sync licenses, link orphans, cleanup playout, find/cleanup duplicates
          * All commands with configurable options and dry-run support
          * No terminal access required
          * Accessible via MEDIA FILES → 🎛️ System Management in admin sidebar (like planung calendar)
        * **License list enhancements**: Video status column in license admin list
          * Shows video availability status (🎬 Available, ⚠️ Not available, ❌ No video)
          * Play link (▶️ Play) for available videos that opens in popup window (800x600px)
          * Optimized queries with select_related to avoid N+1 problems
        * **Video format detection fix**: Improved MIME-type detection for video playback
          * MIME-type now determined by file extension, not ffprobe format
          * Fixes issue where renamed files (e.g., .mov → .mp4) wouldn't play
          * Videos now stream correctly instead of downloading
          * Updated metadata extraction to prioritize file extension over container format
        * **Video availability fix**: Fixed scan command to properly update video availability
          * Existing videos are now always marked as available when found during scan
          * No longer requires --force or --update-metadata flags for availability updates
          * Missing files are automatically marked as unavailable
          * Scan button in admin now works correctly for updating video status
        * **System Management fixes**: Fixed command parameter mismatches and missing functionality
          * Created missing `cleanup_duplicates` command with proper quality-based duplicate removal
          * Fixed parameter mapping for `find_duplicates` command (removed non-existent options)
          * All management commands now work correctly from System Management page
          * Added dry-run protection for destructive operations
      * **Documentation**: Complete automation guide (ADVANCED_FEATURES.md)
    * **NAS/Network Storage Support**: SMB/CIFS mounting for network shares
      * **Development (Docker/macOS)**:
        * Automatic mount scripts (mount_nas.sh, umount_nas.sh)
        * Docker volume configuration for NAS access
        * Test script for verifying access (test_nas_access.sh)
        * Full documentation: media_files/NAS_SETUP.md
      * **Production (Debian 11/gunicorn)**:
        * Automated setup script (deployment/scripts/setup-nas-debian.sh)
        * Support for multiple NAS with different IP addresses
        * fstab and systemd mount unit configurations
        * Health check and remount scripts
        * Full documentation: deployment/NAS_DEBIAN_SETUP.md
        * Quick start: deployment/PRODUCTION_NAS_QUICKSTART.txt
      * Production configs updated with [media] section (ok-bayern, ok-nrw, okmq)
    * Comprehensive video metadata: codec, bitrate, FPS, resolution, color space, chroma subsampling
    * Audio metadata: codec, bitrate, sample rate, channels, channel layout
    * Built-in video player in Django Admin with HTML5 support and seeking
    * Automatic copy from archive to playout when broadcast plans are saved
    * File integrity verification with SHA256 checksums
    * Complete operation history logging
    * Management commands: scan_video_storage, update_video_metadata, copy_to_playout, cleanup_playout
    * Admin actions: copy to playout, update metadata, verify integrity
    * Integration with License model (one-to-one relationship by number)
    * Integration with Planung module for auto-copying videos
    * Configurable via config file (docker.cfg)
    * Supported formats: mp4, mov, mpeg, mpg (configurable)
    * Full documentation:
      * media_files/README.md - Technical documentation
      * media_files/ADMIN_GUIDE.md - Django Admin user guide with examples
      * media_files/QUICKSTART.md - Quick start guide

2025-10-11 (Version 2.4)
========================

* **Performance Audit and Database Optimization**
  * Comprehensive N+1 query elimination across 13+ files
  * Admin pages optimized: 50-90% reduction in query count
  * Example: RentalRequestAdmin reduced from 301 queries to 3 queries (99% improvement)
  * API endpoints optimized: 30-70% faster loading times
 * Dashboard widgets optimized: 20-50% performance improvement
  
* **Admin Panel Query Optimization**
  * RentalRequestAdmin: Added select_related() for user, created_by, user__profile
  * RentalItemAdmin: Optimized FK queries for inventory_item, manufacturer, location
  * LicenseAdmin: Added prefetch_related() for tags, select_related() for profile/category
  * InventoryItemAdmin: Optimized all FK relationships (manufacturer, category, location, owner)
  * ProfileAdmin: Added select_related() for okuser and media_authority
  * ProjectAdmin: Optimized FK and M2M queries with prefetch_related()
  
* **API Endpoint Optimization**
  * api_get_all_rentals: Fixed paginator prefetch_related() loss issue
  * Implemented post-pagination re-optimization to preserve query efficiency
  * api_get_inventory_schedule: Added inventory_item to select_related()
  * api_users_detail: Added select_related() for okuser and media_authority
  * Reduced API response times by 30-70% under load
  
* **Widget and View Optimization**
  * EquipmentSet loops: Added prefetch_related() for items__inventory_item
  * Dashboard view: Added select_related() for profile.media_authority
  * Reduced widget rendering time by 20-50%
  
* **Documentation and Best Practices**
  * Added performance documentation for problematic methods (get_room_summary, get_inventory_number)
  * Created comprehensive PERFORMANCE_AUDIT_REPORT.md
  * Documented paginator prefetch_related() pitfalls
  * Added recommendations for caching and database indexes
  
* **Dashboard Chart Enhancements**
  * Added total count display in chart titles (e.g., "Age Structure (150)")
  * Added individual value labels in Y-axis for all bars
  * Enhanced data visibility in all dashboard graphs
  * Improved user experience with real-time sum calculations
  
* **Admin Filter UI Improvements**
  * Fixed text color and styling of "Reset" buttons in filters
  * Consistent button styling across datetime and numeric range filters
  * Improved button alignment and readability
  * Enhanced UX with proper CSS variable usage for theme compatibility

2025-10-10 (Version 2.3)
========================

* **API Enhancements**
  * Added token-based authentication API endpoint for license metadata
  * Implemented LicenseMetadataSerializer with comprehensive data export
  * Added `targetChannel` field for PeerTube integration (ActivityPub/Fediverse format)
  * Enhanced `originallyPublishedAt` logic with time extraction from planning system
  * Created comprehensive API tests with authorization and data validation

* **Admin Interface Improvements**
  * Enhanced Token Admin with staff-only user filtering and search functionality
  * Added Django AutocompleteSelect for improved user selection experience
 * Implemented API documentation modal with cURL, JavaScript, and Python examples
  * Added copy-to-clipboard functionality for API tokens and examples
  * Fixed Token registration conflicts and improved error handling
  * Enhanced UserAdmin with extended search fields (email, first_name, last_name)

* **Profile Model Updates**
  * Added `ausweisnummer` field for ID document number storage
  * Implemented data sharing permission checkboxes:
    * `phone_data_sharing_allowed` - permission to share phone number with third parties
    * `email_data_sharing_allowed` - permission to share email address with third parties
  * Organized admin fieldsets with collapsible sections for better UX
 * Excluded admin-only fields from user registration and profile edit forms
  * Enhanced ProfileResource for data export with new fields

* **Custom Widget Development**
  * Created TagsInputWidget for improved tags input in Django Admin
  * Replaced default JSONField with user-friendly interface
  * Added real-time tag preview and validation (maximum 4 tags)
  * Implemented interactive tag removal and automatic comma separation
 * Enhanced form validation with empty tag prevention and duplicate removal
 * Added support for null value handling and clean default display

* **Security and Privacy Enhancements**
  * Implemented GDPR-compliant data sharing permissions
  * Added admin-only access controls for sensitive profile fields
  * Enhanced token authentication with secure API endpoints
  * Improved user data protection with selective field exposure

* **Documentation and Testing**
  * Added comprehensive API documentation with usage examples
  * Created detailed admin interface documentation
  * Implemented extensive test coverage for new features
  * Added migration scripts for database schema updates
 * Enhanced inline code documentation and help texts

* **Database Migrations**
  * Added migration for new Profile model fields
  * Updated License model with tags field and default value changes
 * Implemented data migration for existing records
  * Added database indexes for improved search performance

* **Performance Optimizations**
  * Optimized database queries with select_related() and only() methods
  * Added composite indexes on Profile (first_name, last_name) for faster searches
  * Reduced database queries in API endpoints from 5+ to 1-2 per request
  * Implemented query optimization reducing data transfer by ~70%

* **Security Enhancements**
  * Added API rate limiting (10/hour for anonymous, 1000/hour for authenticated users)
  * Implemented comprehensive API access logging with user and IP tracking
  * Enhanced error handling with detailed logging for debugging
  * Added throttling protection against API abuse and DDoS attacks

* **Admin Interface Improvements**
  * Added fieldsets organization to LicenseAdmin (6 sections with collapsible panels)
  * Improved ProjectAdmin fieldsets with collapsible participant sections and descriptions
 * Added fieldsets to InventoryItemAdmin (5 sections grouped by functionality)
  * Enhanced ContributionAdmin with basic fieldsets for consistency
 * Improved UX with logical grouping: Basic Info → Details → Advanced (collapsed)
  * Reduced admin form scrolling by ~50-70% with smart field organization
  * Added helpful descriptions to complex sections (participant validation, auto-calculated fields)
  * Standardized readonly_fields across all admins for better data integrity

* **User Interface Enhancements**
  * Added Tags (Hashtags) field to user-facing License creation form
 * Integrated TagsInputWidget in License edit form for visual tag management
  * Added tag input with comma-separated values and visual badges
  * Implemented tag validation (max 4 tags) in user interface
 * User-friendly tag management with click-to-remove badges
  * Consistent tag experience between admin and user interfaces

* **Deployment Infrastructure Improvements**
  * Restructured deployment configuration with dedicated `deployment/` directory
  * Added comprehensive Docker deployment support with production-ready configuration
  * Added Gunicorn deployment guide with systemd service files
  * Created ready-to-use configurations for multiple German states (Bayern, NRW, OKMQ)
  * Enhanced configuration files with complete organization settings (description, opening_hours, broadcast times)

* **Documentation Enhancements**
  * Translated all deployment documentation to English
  * Added detailed deployment guides for Docker and Gunicorn methods
  * Created architecture diagrams and deployment comparison tables
  * Updated GitHub repository references throughout the codebase
  * Enhanced configuration file comments with complete state media institution list

* **Configuration Management**
  * Expanded organization configuration with new fields:
    * `description` - Organization description for welcome page
    * `opening_hours` - Formatted opening hours with line breaks
    * `broadcast_start` / `broadcast_end` - Broadcast slot configuration
  * Unified configuration structure across Docker and Gunicorn deployments
  * Added detailed inline documentation for all configuration options

* **Codebase Cleanup**
  * Removed deprecated example configurations from project root
  * Removed outdated systemd service files from scripts/ directory
  * Removed accidentally included odfpy man-pages (share/ directory)
  * Removed legacy development scripts (createsuperuser.py, test_data.py, etc.)
  * Consolidated all deployment-related files under `deployment/` directory
  * Unified requirements files: removed requirements-docker.txt, using single requirements.txt
  * Removed unused reportlab dependency

* **Security and Production Readiness**
  * Enhanced systemd service files with comprehensive security settings
  * Added production-specific environment variable handling
 * Improved SSL/HTTPS configuration examples
 * Added rate limiting and health check configurations for Nginx
  * Enhanced Docker security with user isolation and minimal privileges

2025-09-21
==========

* **Dashboard Analytics System** - Added comprehensive dashboard with interactive charts
  * Multiple chart types: doughnut, bar, horizontal bar with dynamic switching
  * Real-time data visualization for users, projects, licenses, and inventory
 * Export functionality for all chart data
  * Responsive design with adaptive height for large datasets

* **Admin Interface Enhancements**
  * Added direct dashboard link in Django admin menu
 * Hidden specific admin models (Alert Logs, Alert Thresholds, Funnel Metrics, User Journey Stages)
  * Improved admin navigation and user experience

* **Translation System Improvements**
  * Updated German and English translation files (.po/.mo)
  * Added chart-related translations (Doughnut Chart, Bar Chart, Horizontal Bar Chart)
  * Fixed translation compilation issues
  * Added dashboard-specific translation files

* **Chart System Features**
  * Extended color palette (15 colors) to prevent repetition
  * Adaptive container height based on data amount
  * Improved legend display with label truncation
  * Horizontal bar chart support with proper axis configuration
  * Enhanced tooltip functionality

* **Code Quality Improvements**
  * Updated .gitignore to exclude development files
  * Fixed JavaScript translation import issues
  * Improved error handling in dashboard widgets
  * Enhanced responsive design for mobile devices

2023-06-27
==========

* Change the "Nutzeranmeldung" pdf to a more recent version.

* Fix the gender count validation to include all genders which can be selected.
