# Long Maintenances in the Calendar and iCal Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draw maintenances longer than 24 h as label-safe bands behind short events, and add a `duration_min` / `duration_max` filter to the API, the iCal feed and the calendar page.

**Architecture:** The filter is two `NumberFilter`s on `MaintenanceFilterSet` over an annotated `end - start`; the iCal view runs the same filterset rather than re-implementing it. In the calendar, FullCalendar keeps the grid, toolbar, navigation and data fetching, but events are loaded with `display: 'none'` and drawn by plugin code: a pure layout module (`calendar-lib.js`, unit-tested with `node --test`) packs each week row into fixed-height lanes, and `calendar.js` renders the result as an absolutely positioned layer per row. This gives exact control over the "label half never covered" rule, which FullCalendar's own row stacking cannot express.

**Tech Stack:** Django / NetBox 4.4-4.5 plugin, django-filter, pytest + pytest-django, FullCalendar v6.1.19 (vendored global bundle), plain browser JS, Node 22 `node:test` (no npm dependencies).

**Spec:** `docs/superpowers/specs/2026-10-28-long-maintenance-calendar-design.md`

## Global Constraints

- Long means `end - start > 24 hours`; the 24 h band cutoff is fixed in code and independent of the hide threshold.
- Band height is 2x a normal event bar, always, including when bands stack.
- A band's bottom half (the label) is never covered; its top half is a slot for at most one short event.
- Duration filter bounds are inclusive, in hours, fractional allowed; absent parameters mean no filtering.
- Invalid iCal duration value returns 400.
- Hide switch is off by default; when on, the page URL carries `?duration_max=<N>` (default N = 24); Subscribe and Download links carry it too.
- No plugin setting for a default threshold. No change to outages, the event modal, or the GraphQL filter.
- ASCII-only in code, comments, docs and commit messages. No issue numbers in source comments or docstrings (test docstrings may cite #85).
- Every pytest run: `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest ...` from the plugin root.
- Lint: `/opt/netbox/venv/bin/ruff check notices tests` and `/opt/netbox/venv/bin/ruff format --check notices tests`.
- Commits on the feature branch `feat/long-maintenance-calendar` only; Conventional Commits; no AI attribution; never `--no-verify`.

## Review Focus

1. A maintenance whose end is exactly local midnight must not occupy the next day's column (end is exclusive), or bands gain a phantom day. Pinned in Task 3 (`segmentForRow` midnight test).
2. A week spanning a DST change (23 h or 25 h day) must still map dates to the right columns. Pinned in Task 3 (DST test).
3. A short maintenance that crosses midnight spans two columns and needs a lane free in both. Pinned in Task 3 (`layoutRow` two-column short test).
4. Bad hide-threshold input in the page URL or the number box (`abc`, `-5`, `0`, empty) must not break the page or send a bad API request. Pinned in Task 3 (`parseHours` tests) and used in Task 5.
5. `duration_max=-1` on the API or iCal feed must be rejected, not silently return nothing. Pinned in Task 1 (filterset) and Task 2 (iCal 400).

---

## File Structure

- Modify `notices/filtersets.py`: `duration_min`, `duration_max` on `MaintenanceFilterSet`.
- Modify `notices/forms.py`: same two fields on `MaintenanceFilterForm`.
- Modify `notices/views.py`: `MaintenanceICalView` parses and applies the duration params.
- Create `notices/static/notices/js/calendar-lib.js`: pure functions (no DOM): segmenting, lane layout, hours parsing.
- Modify `notices/static/notices/js/calendar.js`: render the layout, hide switch, URL state, feed links.
- Modify `notices/static/notices/css/calendar-overrides.css`: band and short-event styles.
- Modify `notices/templates/notices/calendar.html`: switch markup, load `calendar-lib.js`.
- Modify `Makefile`: `test-js` target.
- Create `tests/test_duration_filter.py`; modify `tests/test_ical_view.py`; create `tests/js/calendar-lib.test.js`.
- Docs: `docs/api/rest-api.md`, `docs/events/calendar-and-ical.md`, `README.md`, `CHANGELOG.md`.

---

### Task 1: Duration filter on the maintenance filterset and filter form

**Files:**
- Modify: `notices/filtersets.py` (`MaintenanceFilterSet`, around lines 24-100)
- Modify: `notices/forms.py:230-258` (`MaintenanceFilterForm`)
- Test: `tests/test_duration_filter.py` (create)
- Docs: `docs/api/rest-api.md` (Maintenance "Filters" table, around line 76), `CHANGELOG.md` `[Unreleased]` / `### Added`

**Interfaces:**
- Produces: `MaintenanceFilterSet` accepts `duration_min` and `duration_max` (hours, decimal, `min_value=0`); invalid values make `filterset.is_valid()` False. Task 2 relies on this.

- [ ] **Step 1: Create the branch**

Run: `git switch -c feat/long-maintenance-calendar main`

- [ ] **Step 2: Write the failing tests** in `tests/test_duration_filter.py`, `@pytest.mark.django_db`, using the existing `provider` fixture. A local helper `_maint(provider, name, hours)` creates a CONFIRMED maintenance with `start=timezone.now()` and `end=start + timedelta(hours=hours)`. Filter with `MaintenanceFilterSet(data, queryset=Maintenance.objects.all()).qs` and compare `set(qs.values_list("name", flat=True))`.

```python
def test_duration_max_is_inclusive(provider):
    _maint(provider, "M24", 24); _maint(provider, "M25", 25)
    assert names({"duration_max": "24"}) == {"M24"}

def test_duration_min_is_inclusive(provider):
    _maint(provider, "M2", 2); _maint(provider, "M24", 24); _maint(provider, "M25", 25)
    assert names({"duration_min": "24"}) == {"M24", "M25"}

def test_fractional_hours(provider):
    _maint(provider, "M90MIN", 1.5)
    assert names({"duration_max": "1.5"}) == {"M90MIN"}
    assert names({"duration_max": "1.4"}) == set()

def test_min_and_max_combined(provider):
    _maint(provider, "M2", 2); _maint(provider, "M24", 24); _maint(provider, "M25", 25)
    assert names({"duration_min": "2.5", "duration_max": "24"}) == {"M24"}

def test_negative_duration_is_invalid():
    fs = MaintenanceFilterSet({"duration_max": "-1"}, queryset=Maintenance.objects.all())
    assert not fs.is_valid()
```

- [ ] **Step 3: Run them to verify they fail**

Run: `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest tests/test_duration_filter.py -v`
Expected: the four filtering tests FAIL (unknown filters are ignored, so extra rows come back); `test_negative_duration_is_invalid` FAILS (`is_valid()` is True).

- [ ] **Step 4: Implement** in `MaintenanceFilterSet`:

`duration_min` and `duration_max` as `django_filters.NumberFilter(method="filter_duration", min_value=0, label="Min duration (hours)" / "Max duration (hours)")`, and one method `filter_duration(self, queryset, name, value) -> QuerySet` that annotates `event_duration=ExpressionWrapper(F("end") - F("start"), output_field=DurationField())` and filters `event_duration__gte` for `duration_min` / `event_duration__lte` for `duration_max` with `timedelta(hours=float(value))`. Annotate, do not add a model field (the spec rules out a stored generated column because Django 5.2 does not refresh it on UPDATE). Add a short comment saying why the annotation is used.

- [ ] **Step 5: Run the tests to verify they pass**

Run: same command as Step 3. Expected: 5 passed.

- [ ] **Step 6: Add the form fields** to `MaintenanceFilterForm`: `duration_min` and `duration_max` as `forms.DecimalField(required=False, min_value=0, label=...)` matching the filterset labels, and add both names to the `"Attributes"` `FieldSet`. No test: these are declarations with no plugin logic.

- [ ] **Step 7: Docs.** In `docs/api/rest-api.md` add rows to the Maintenance filter table: `duration_min` / `duration_max` -- "Maintenances lasting at least / at most N hours (`end - start`), inclusive; fractional values allowed, e.g. `?duration_max=24`". In `CHANGELOG.md` under `[Unreleased]` / `### Added`: "`duration_min` and `duration_max` maintenance filters (hours) in the REST API and the maintenance list. (#85)".

- [ ] **Step 8: Lint, then commit**

```bash
/opt/netbox/venv/bin/ruff check --fix notices tests && /opt/netbox/venv/bin/ruff format notices tests
git add notices/filtersets.py notices/forms.py tests/test_duration_filter.py docs/api/rest-api.md CHANGELOG.md
git commit -m "feat(filters): filter maintenances by duration" -m "Refs #85"
```

---

### Task 2: Duration filter on the iCal feed

**Files:**
- Modify: `notices/views.py` (`MaintenanceICalView`: class docstring around line 512, `_parse_query_params` around line 676, `_build_queryset` around line 706)
- Test: `tests/test_ical_view.py` (new class `TestMaintenanceICalViewDurationFilter`, same `setup_method` as `TestMaintenanceICalViewFiltering`)
- Docs: `docs/events/calendar-and-ical.md` (query parameter table, around line 43), `CHANGELOG.md`

**Interfaces:**
- Consumes: `MaintenanceFilterSet` duration filters from Task 1.
- Produces: `/plugins/notices/ical/maintenances.ics?duration_min=&duration_max=`. Task 5 appends `duration_max` to the feed URLs.

- [ ] **Step 1: Write the failing tests.** Each creates `SHORT` (2 h) and `LONG` (72 h) maintenances starting now, CONFIRMED.

```python
def test_duration_max_filters_feed(self):
    # no param: both present (existing subscriptions unchanged)
    assert "SHORT" in body() and "LONG" in body()
    content = body("&duration_max=24")
    assert "SHORT" in content and "LONG" not in content

def test_duration_min_filters_feed(self):
    content = body("&duration_min=24")
    assert "LONG" in content and "SHORT" not in content

def test_invalid_duration_returns_400(self):
    assert get("&duration_max=abc").status_code == 400
    assert get("&duration_max=-1").status_code == 400

def test_etag_differs_with_duration_filter(self):
    assert get("")["ETag"] != get("&duration_max=24")["ETag"]
```

`get(extra)` requests `/plugins/notices/ical/maintenances.ics?token=<plaintext>{extra}`; `body(extra)` returns its decoded content. Docstring of the class may cite #85.

- [ ] **Step 2: Run them to verify they fail**

Run: `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest tests/test_ical_view.py -k Duration -v`
Expected: filter tests FAIL (`LONG` / `SHORT` still present), 400 test FAILS (200), ETag test FAILS (equal tags).

- [ ] **Step 3: Implement.**
  - `_parse_query_params`: copy `duration_min` / `duration_max` from `request.GET` into `params` as the raw strings when present. Because `params` feeds `calculate_etag`, the tag changes with the filter for free.
  - `_build_queryset`: when either key is in `params`, run `filtersets.MaintenanceFilterSet({k: params[k] for k in present}, queryset=queryset)`; if `not fs.is_valid()` raise `ValueError(f"Invalid duration filter: {...}")` built from `fs.errors` (the existing `get()` already turns `ValueError` into 400); otherwise `queryset = fs.qs`. Do not re-implement the duration arithmetic.
  - Add the two parameters to the class docstring's parameter list.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest tests/test_ical_view.py -v`
Expected: all pass, including the pre-existing iCal tests.

- [ ] **Step 5: Docs.** Add `duration_min` and `duration_max` rows to the query-parameter table in `docs/events/calendar-and-ical.md` (default `--`, "Only maintenances lasting at least / at most N hours, inclusive, fractional allowed. Invalid or negative values return `400`."), and extend the example subscription URL with `&duration_max=24`. Extend the Task 1 CHANGELOG entry to say "REST API, the maintenance list and the iCal feed".

- [ ] **Step 6: Lint, then commit**

```bash
git add notices/views.py tests/test_ical_view.py docs/events/calendar-and-ical.md CHANGELOG.md
git commit -m "feat(ical): accept duration_min and duration_max on the feed" -m "Refs #85"
```

---

### Task 3: Pure calendar layout module

**Files:**
- Create: `notices/static/notices/js/calendar-lib.js`
- Create: `tests/js/calendar-lib.test.js`
- Modify: `Makefile` (add `test-js`)

**Interfaces:**
- Produces (global `window.NoticesCalendar` in the browser, `module.exports` under Node, via a small UMD wrapper; no DOM access):
  - `LONG_THRESHOLD_MS = 24 * 3600 * 1000`
  - `isLong(start: Date, end: Date) -> boolean` -- `end - start > LONG_THRESHOLD_MS`.
  - `segmentForRow(start: Date, end: Date, rowStart: Date, nDays: number) -> {startCol, endCol, startsHere, endsHere} | null` -- columns are local calendar days, `rowStart` is local midnight of the row's first day; `end` is exclusive (an end at exactly local midnight belongs to the previous day; a zero-length event occupies its start day); `null` when the event does not touch the row. Day index = `Math.round((localMidnight(d) - rowStart) / 86400000)` so 23 h and 25 h DST days map correctly. `startsHere` / `endsHere` say whether the real start / end falls inside the row (drives the band edges).
  - `layoutRow(segs: Array<{id, startCol, endCol, long: boolean}>) -> {placements: Array<{id, lane}>, laneCount: number}` -- input order is the tie-breaker (caller passes events sorted by start, then longer first). Algorithm, in lanes of one event-height each:
    1. Long segs, in order: band row `k` is the lowest row with no other band overlapping its columns; it occupies lanes `2k` (slot) and `2k+1` (label).
    2. Every label lane cell `(2k+1, col)` covered by a band is blocked.
    3. Short segs, in order: the lowest lane `L` that is free (not blocked, not taken by a short) in every column `startCol..endCol`.
    4. `laneCount` = highest lane used + 1 (0 for an empty row).
  - `parseHours(value: string | null) -> number | null` -- finite number `> 0`, else `null`.

- [ ] **Step 1: Write the failing tests** with `node:test` and `node:assert/strict`, requiring `../../notices/static/notices/js/calendar-lib.js`. Dates are built with `new Date(y, m, d, h)` (local time). Run them under `TZ=America/Toronto` (Step 2) so the DST case is real.

```js
test('isLong is strict at 24h', () => {
  assert.equal(isLong(d(2026,9,5,0), d(2026,9,6,0)), false);
  assert.equal(isLong(d(2026,9,5,0), d(2026,9,6,0,1)), true);
});
test('segmentForRow: end at local midnight does not touch the next day', () => {
  // row Mon 2026-10-05; event Tue 09:00 -> Thu 00:00
  assert.deepEqual(segmentForRow(d(2026,9,6,9), d(2026,9,8,0), d(2026,9,5), 7),
    {startCol: 1, endCol: 2, startsHere: true, endsHere: true});
});
test('segmentForRow: event continuing into next row has no end here', () => {
  const s = segmentForRow(d(2026,9,8,9), d(2026,9,14,18), d(2026,9,5), 7);
  assert.deepEqual(s, {startCol: 3, endCol: 6, startsHere: true, endsHere: false});
  assert.deepEqual(segmentForRow(d(2026,9,8,9), d(2026,9,14,18), d(2026,9,12), 7),
    {startCol: 0, endCol: 2, startsHere: false, endsHere: true});
});
test('segmentForRow: event outside row is null', () => { /* ends before rowStart -> null */ });
test('segmentForRow: DST week maps days correctly', () => {
  // Toronto DST ends Sun 2026-11-01; row Mon 2026-10-26
  assert.equal(segmentForRow(d(2026,10,2,1), d(2026,10,2,3), d(2026,9,26), 14).startCol, 7);
});
test('layoutRow: one band plus three shorts on its first day', () => {
  // band cols 1-4; three shorts on col 1
  // -> band lane 0, shorts lanes 0, 2, 3 (lane 1 is the label)
});
test('layoutRow: three stacked bands fill their slots', () => {
  // bands cols 1-5, 2-4, 2-5; three shorts on col 3 -> bands lanes 0,2,4; shorts 0,2,4
});
test('layoutRow: short spanning two columns needs both free', () => {
  // band cols 2-4 (lanes 0-1); short A col 1 lane 0; short B cols 1-2 -> lane 2
  // (lane 0 taken at col 1, lane 1 blocked at col 2)
});
test('layoutRow: empty row', () => assert.deepEqual(layoutRow([]), {placements: [], laneCount: 0}));
test('parseHours', () => {
  assert.equal(parseHours('24'), 24); assert.equal(parseHours('1.5'), 1.5);
  for (const v of ['abc', '-5', '0', '', null]) assert.equal(parseHours(v), null);
});
```

(Fill the commented cases with exact `deepEqual` assertions on `placements` and `laneCount`; the expected lanes are stated in each comment.)

- [ ] **Step 2: Run them to verify they fail**

Run: `TZ=America/Toronto node --test tests/js/`
Expected: FAIL with "Cannot find module .../calendar-lib.js".

- [ ] **Step 3: Implement** `calendar-lib.js` with the signatures above (UMD wrapper: `module.exports` when `module` exists, else `window.NoticesCalendar`). Plain ES2020, no dependencies, no DOM.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `TZ=America/Toronto node --test tests/js/` and `TZ=UTC node --test tests/js/`
Expected: all pass in both time zones.

- [ ] **Step 5: Add the Makefile target** `test-js` (with a `## Run calendar JS unit tests` help comment and `.PHONY`) running `TZ=America/Toronto node --test tests/js/`.

- [ ] **Step 6: Commit**

```bash
git add notices/static/notices/js/calendar-lib.js tests/js/calendar-lib.test.js Makefile
git commit -m "feat(calendar): add lane layout for long maintenances" -m "Refs #85"
```

---

### Task 4: Render bands and short events in the calendar

**Files:**
- Modify: `notices/static/notices/js/calendar.js`
- Modify: `notices/static/notices/css/calendar-overrides.css`
- Modify: `notices/templates/notices/calendar.html` (load `calendar-lib.js` before `calendar.js`)
- Docs: `docs/events/calendar-and-ical.md` (Interactive calendar section), `README.md` (Calendar View bullets), `CHANGELOG.md` `### Changed`

**Interfaces:**
- Consumes: `window.NoticesCalendar.{isLong, segmentForRow, layoutRow}` from Task 3.
- Produces: `renderEventLayer(calendar)` in `calendar.js`, which Task 5 does not change; Task 5 only changes what is fetched.

- [ ] **Step 1: Switch FullCalendar to data-only for events.** Keep the existing `events` function and mapping, but give every mapped event `display: 'none'` so FullCalendar stores them (`calendar.getEvents()`) without drawing them. Remove `displayEventTime` / `displayEventEnd` (no longer used) and the `eventClick` option (clicks move to the layer).

- [ ] **Step 2: Implement `renderEventLayer(calendar)`**, scheduled through `requestAnimationFrame` from the `eventsSet` and `datesSet` callbacks. For each week row (`.fc-daygrid-body tr` in the current view; works for `dayGridMonth` and `dayGridWeek`):
  - `rowStart` from the first cell's `data-date` (parsed as local midnight), `nDays` = number of `td.fc-daygrid-day` cells.
  - For every event, `segmentForRow(...)`; sort by start, then longer first; call `layoutRow`.
  - Remove any previous layer, then append one `div.notices-layer` inside the first cell's `.fc-daygrid-day-events` (made `position: relative`), `width: nDays * 100%`, absolute at the top. Set `min-height` of every cell's `.fc-daygrid-day-events` in the row to `laneCount * LANE_PX` so the row grows to fit.
  - Each placement becomes an absolutely positioned `<a>` with `left = startCol / nDays * 100%`, `width = (endCol - startCol + 1) / nDays * 100%`, `top = lane * LANE_PX`. Long: class `notices-band`, height `2 * LANE_PX`, plus `notices-band--start` when `startsHere` and `notices-band--end` when `endsHere`, label (event title) in the bottom half, CSS variable `--notices-c: var(--tblr-<status_color>)`. Short: classes `fc-event fc-h-event fc-daygrid-event fc-daygrid-block-event notices-short` so it inherits FullCalendar's block look, background the status color, text `HH:MM title` on its start segment and `title` on a continuation segment.
  - Each element gets a `title` attribute (full title and start/end) and a click handler calling the existing `showEventModal(event)` with the FullCalendar `EventApi`.

- [ ] **Step 3: CSS** in `calendar-overrides.css`: `LANE_PX` matches the CSS custom property `--notices-lane: 22px` (read it once with `getComputedStyle` so the two cannot drift). `.notices-band`: background `color-mix(in srgb, var(--notices-c) 18%, transparent)`, text `color-mix(in srgb, var(--notices-c) 70%, black)`, label aligned to the bottom, `z-index: 1`. `.notices-band--start` / `--end`: `3px solid var(--notices-c)` left / right border. `.notices-short`: `z-index: 2`, one lane high, ellipsis. A short in lane `2k` on a band's start column is inset by the 3px edge width (`margin-left: 3px` when its left aligns with a `--start` band; compute in JS and add class `notices-short--inset`). Dark theme: keep the text readable, e.g. mix with white under `[data-bs-theme=dark]`.

- [ ] **Step 4: Manual verification** (no JS DOM test harness in this repo; the layout rules are covered by Task 3). Run `make runserver`, create maintenances reproducing the approved mockups (`.superpowers/brainstorm/3804118-1793195355/content/final-v2.html`), and check in both Month and Week views:
  - [ ] a lone band crossing a week boundary has its start edge, its end edge on the next row, and no edge at the break;
  - [ ] one band plus three short events on the same day: one short in the slot, two below the band, label readable;
  - [ ] three overlapping bands plus three short events on one day: shorts in the three slots, all labels readable;
  - [ ] a short event and a long one both starting at 02:00: short inset inside the start edge;
  - [ ] clicking a band and a short event opens the modal with the right content;
  - [ ] light and dark theme; navigation prev/next/today re-renders correctly; window resize keeps alignment.
  Capture screenshots of Month and Week views for the PR.

- [ ] **Step 5: Docs.** In `docs/events/calendar-and-ical.md` describe the band rendering (over 24 h, fixed; label never covered; edges mark the real start and end) and correct the stale "month, week, and day modes" to month and week. In `README.md` fix the Calendar View bullets the same way and add one bullet for long-maintenance bands; also correct the stale iCal parameter list there (`days_past` / `days_future` / `provider` by ID) to the real `past_days`, `provider`, `provider_id`, `status`, `duration_min`, `duration_max`, and point to `docs/events/calendar-and-ical.md`. CHANGELOG `### Changed`: "Calendar: maintenances longer than 24 hours are drawn as light bands behind short events, so they no longer crowd out short windows. (#85)".

- [ ] **Step 6: Commit**

```bash
git add notices/static/notices/js/calendar.js notices/static/notices/css/calendar-overrides.css notices/templates/notices/calendar.html docs/events/calendar-and-ical.md README.md CHANGELOG.md
git commit -m "feat(calendar): draw long maintenances as bands behind short ones" -m "Refs #85"
```

---

### Task 5: "Hide longer than N h" switch

**Files:**
- Modify: `notices/templates/notices/calendar.html` (`{% block control-buttons %}`)
- Modify: `notices/static/notices/js/calendar.js`
- Docs: `docs/events/calendar-and-ical.md`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `NoticesCalendar.parseHours` (Task 3), `duration_max` on the API (Task 1) and the feed (Task 2).

- [ ] **Step 1: Markup.** In `control-buttons`, before the Subscribe button: a Tabler `form-check form-switch` (`id="hideLongSwitch"`) labelled "Hide longer than", an `input type="number"` (`id="hideLongHours"`, `min="0"`, `step="any"`, `value="24"`, `form-control form-control-sm`, narrow), and the text "h".

- [ ] **Step 2: State.** On load, `parseHours(new URLSearchParams(location.search).get('duration_max'))`: a number turns the switch on and fills the box; `null` leaves it off with 24. Helper `hideThreshold() -> number | null` returns the active threshold (switch on and `parseHours(box) !== null`), else `null`.

- [ ] **Step 3: Wire it.**
  - The `events` fetch adds `duration_max=<hideThreshold()>` when not `null`.
  - On switch change or box `change`: if the switch is on and the box is invalid, leave everything as it was (no fetch, no URL change); otherwise update the page URL with `history.replaceState` (set or delete `duration_max`, keep any other params) and call `calendar.refetchEvents()`.
  - The Subscribe URL and the Download URL append `&duration_max=<n>` when `hideThreshold()` is not `null`.
  - The band cutoff stays `LONG_THRESHOLD_MS`; nothing here touches it.

- [ ] **Step 4: Manual verification.**
  - [ ] Off by default, URL unchanged, long maintenances shown as bands.
  - [ ] On with 24: URL gets `?duration_max=24`, long maintenances disappear; set 72: a 48 h one returns as a band.
  - [ ] Reloading `?duration_max=72` starts with the switch on and 72 in the box.
  - [ ] `?duration_max=abc` loads with the switch off and no console error; typing `-5` or clearing the box while on changes nothing.
  - [ ] The Subscribe modal URL and the Download link include `duration_max` only when on.

- [ ] **Step 5: Docs.** Describe the switch, the URL parameter and the feed links in `docs/events/calendar-and-ical.md`. CHANGELOG `### Added`: "Calendar: 'Hide longer than N h' switch, kept in the page URL and applied to the Subscribe and Download links. (#85)".

- [ ] **Step 6: Commit**

```bash
git add notices/templates/notices/calendar.html notices/static/notices/js/calendar.js docs/events/calendar-and-ical.md CHANGELOG.md
git commit -m "feat(calendar): add a switch to hide long maintenances" -m "Refs #85"
```

---

### Task 6: Branch verification and PR

- [ ] **Step 1: Full suite with coverage**

Run: `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest tests/ --cov=notices --cov-report=xml -q` and `make test-js`
Expected: all green.

- [ ] **Step 2: Lint**

Run: `/opt/netbox/venv/bin/ruff check notices tests && /opt/netbox/venv/bin/ruff format --check notices tests`
Expected: clean.

- [ ] **Step 3: Diff coverage**

Run: `uv tool run diff-cover coverage.xml --compare-branch main`
Expected: changed Python lines at or above the project average (about 83%).

- [ ] **Step 4: DRY review.** Dispatch a review subagent on the Fable model (`feature-dev:code-reviewer`, `model: "fable"`) scoped to `git diff main...HEAD`, mandate: duplicated logic, copy-paste, parallel implementations. Report its findings to the user; do not apply them silently.

- [ ] **Step 5: Push and open a draft PR** (only after the user approves pushing): title `feat(calendar): de-emphasize and filter long maintenances`, body in the repo template with the Month and Week screenshots, `Refs: #85`. Mark ready when CI is green.
