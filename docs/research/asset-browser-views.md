# Asset browser gallery/list workstream

General Project browser enhancement on our supported Jackdaw dev/0.20 line.

- Entire asset tiles/rows own the standard filename Tooltip + Hovered components.
  Titles use the complete filename and extension, without directory components,
  following existing Project browser conventions. Duplicate image-label popovers
  are removed. Existing separate search-result folder captions remain.
- Native segmented Gallery/List controls select one shared ProjectWindowState
  presentation. Gallery is the default; folder navigation/panel recreation retain
  the mode for the session. No preference storage or restart persistence added.
- List rows use existing feathers list-row/ListBox widgets and ThumbnailSlot/cache.
  They show thumbnails/icons, full names with character wrapping, and modification
  timestamps formatted by the already-resolved chrono crate as YYYY-MM-DD HH:mm UTC.
  Unavailable timestamps show an em dash. No custom date/calendar implementation.
- Filesystem metadata is read during directory refresh, not each frame. Watcher
  refresh now includes file data changes so displayed modification times update.
- Existing browser selection, open, rename, context menu and drag/drop handlers are
  reused; native list selection routes to the same file selection. Switching views
  retains filters, selection and inspector subject and reveals the selected item.
- Existing generic gallery truncation now cuts Unicode on character boundaries.

## Focused evidence

One asset-browser regression passed: Gallery/List transitions retain selection,
search, entries and rename subject without requesting a rescan; missing and epoch
timestamps display correctly; gallery/list entries expose full Unicode filename
tooltips at their roots and list text preserves the full name.

Editor executable built successfully. An independent 20-second 60 Hz review on a
dedicated port checked project and executable identity before commands. It verified
actual thumbnail hover displays reed_clump_0.bsn, both modes render, timestamps
are labelled UTC, and a long Unicode filename survives switching/selection. The
initial layout review exposed unbroken-name overflow; character wrapping and a
shrinkable breadcrumb bar fixed the list/date collision. A second bounded review
confirmed the list name wraps in its column (586 x 66 physical pixels for the
stress name), while the modified-time column stays separate. Final selected-mode
paint uses the existing segmented::segment_background helper and compiled.

No broad suite. Synthetic pointer movement logs an existing Wayland cursor-warp
warning, but injected hover and the actual tooltip were observed. Extremely long
filenames still expose pre-existing clipping/wrapping limitations in unrelated
file-inspector/status labels; this work does not redesign those panels.

Local evidence: /tmp/jackdaw-asset-views-review.json and
/tmp/jackdaw-flicker-asset-browser-views.log. No live scene edits or shared binary
replacement. Shared editor/pin promotion is a separate idle-editor step.
