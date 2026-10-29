# Long maintenances in the calendar and iCal feed

Date: 2026-10-28
Issue: https://github.com/jsenecal/netbox-notices/issues/85

## Intent

Multi-day maintenances (more than 24 hours) flood the calendar. Data-center
providers announce facility work (UPS, HVAC, generator tests) as a single
maintenance spanning days or weeks. In the month view each one is a full
solid bar on every day of its window, so a few of them take most of the rows
and push the short windows the NOC actually acts on (a 00:00-06:00 carrier
splice) down the cell. The same clutter reaches Outlook/Google through the
iCal feed.

The fix has two halves that work together:

1. **De-emphasize** long maintenances in the calendar so they stay visible
   but stop competing with short ones.
2. **Filter** by duration, so people who do not want the long ones at all can
   drop them from the calendar page, the API, and the iCal feed.

## Goals

- Long maintenances never push short maintenances out of a day cell.
- Long maintenances stay visible (by default), remain clickable, and their
  label is never hidden by short events.
- A duration filter on the maintenance API, the iCal feed, and the calendar
  page, with the calendar choice kept in the page URL so it can be bookmarked.

## Non-goals

- No change to the event detail modal content.
- No change to outages. Outages can be open-ended (`end` nullable) and are
  not in the calendar.
- No plugin setting for a default threshold.

## Anti-goals

- Hiding long maintenances by default. Existing users and existing iCal
  subscriptions must see the same set of events as before unless they opt in.
- A solution that makes long maintenances unclickable or unreadable.

## Part 1: calendar rendering of long maintenances (decided)

A maintenance is "long" when `end - start > 24 hours`. The 24 h band cutoff
is **fixed** in code; it is not tied to the hide threshold below and is not
configurable.

Long maintenances are drawn as a **band behind the normal events** (agreed
mockups "D with start and end edges" and "Bands 2x, label half never
covered"):

- Height is decided **per week row**: **1x** a normal event bar when no short
  event sits on the band in that row, **2x** (mockup: 36px band) when one
  does. A maintenance crossing a week break can be 1x in one row and 2x in
  the next. (Revised after the first draft of the PR, which drew every band
  2x.)
- Very light tint of the maintenance's existing status color
  (`var(--tblr-<status_color>)`), roughly 18% opacity. Text in a darker shade
  of the same color.
- A 2x band has two halves. The **top half** is a slot holding the short
  event that sits on it. The **bottom half** holds the label (same title text
  as today: `name - provider (N Impacted)`) and is **never covered** by
  anything. A 1x band is its label alone, and nothing is drawn over it.
- A **solid 3px vertical edge** in the full status color at the segment that
  contains the real start, and at the segment that contains the real end.
  Where a band is cut by a week boundary (FullCalendar splits multi-week
  events into per-row segments), the cut side has **no** edge, so
  "continues" and "ends here" are distinguishable. A short event sitting in
  the slot on the band's first day is inset so the start edge stays visible.
- Short maintenances (24 h or less) look exactly as today and sit on top of
  (z-order above) the band whose slot they occupy.
- When several long maintenances share a day, their bands stack one per row,
  each 1x or 2x by the rule above, like normal multi-day events do.
- Placement of short events on a day that has bands: they fill the top-half
  slots of that day's bands in order (first band, second band, ...), one per
  slot. Once every slot is taken, the remaining short events go below the
  last band, as normal rows. A short that ends up in a free lane instead (for
  example above a band, on a day an earlier band has already ended) does not
  make any band 2x. So a long maintenance's label is never hidden,
  whatever the number of short events (mockup "Bands 2x, label half never
  covered": one band + three short events puts one in the slot and two
  below; three bands + three short events fills the three slots).
- Two maintenances starting at the same time (one short, one long) follow the
  same rule: the short one takes the band's slot.
- Applies in both views the toolbar offers, `dayGridMonth` and `dayGridWeek`
  (same day-grid layout; my call). Screenshots of both go in the PR.
- Clicking a band opens the same modal as clicking a normal event
  (`showEventModal`).

FullCalendar's dayGrid stacks events in separate rows by default, so drawing
short events into a band's slot is expected to need custom work (event classNames
plus CSS positioning, background-event rendering with custom content, or an
`eventDidMount` / `eventContent` hook). The technique is the builder's call;
the visual result above is what was approved.

## Part 2: duration filter (decided)

### API

`MaintenanceFilterSet` gains two filters:

- `duration_min` (hours): keep maintenances whose `end - start >= value`.
- `duration_max` (hours): keep maintenances whose `end - start <= value`.

Both bounds are inclusive. Values may be fractional (`1.5`). Invalid
(non-numeric) values are rejected the same way the filterset rejects other
bad values. `Maintenance.end` is non-null, so duration is always defined.

The same two fields are added to `MaintenanceFilterForm` (`notices/forms.py`)
so the maintenance list view shows a visible control for them, following the
plugin's convention that filterset fields have a matching form field (my
call). The GraphQL `MaintenanceFilter` is **not** extended in this change (my
call; it is defined separately from the filterset).

The calendar already fetches `/api/plugins/notices/maintenance/?end__gte=...&start__lte=...&limit=0`,
so it gets the filter for free.

### iCal feed

`MaintenanceICalView` (`notices/views.py`) accepts `duration_min` and
`duration_max` with the same meaning, next to `provider`, `provider_id`,
`status`, `past_days`. Absent parameters mean no duration filtering, so
existing subscriptions are unchanged. An invalid value returns 400, like an
invalid `provider_id`. The parsed values are part of `params`, so they feed
into the ETag (`calculate_etag(params=...)`) and two differently filtered
feeds never share a tag. Prefer reusing the filterset's logic over writing a
second duration implementation.

### Calendar page toggle

- In the calendar page header, next to the existing Subscribe and Download
  buttons: a switch labelled "Hide longer than [N] h" with an editable number
  input. Default N is 24, default switch state is off.
- Off: the page URL has no duration parameter; long maintenances render as
  bands (Part 1).
- On: the page URL carries `?duration_max=<N>` (updated in place, e.g.
  `history.replaceState`, no full reload required). The calendar's API fetch
  adds `duration_max=<N>`, so longer maintenances are not loaded. Editing N
  while on updates both.
- Loading the page with `?duration_max=<N>` in the URL starts with the switch
  on and N filled in.
- The Subscribe URL and the Download link also carry `duration_max=<N>` when
  the switch is on, so the copied feed matches what is on screen.
- The band cutoff stays 24 h regardless of N. If N is, say, 72, maintenances
  between 24 h and 72 h still render as bands.

## Docs

- `docs/events/calendar-and-ical.md`: bands, the toggle, the new iCal params.
- API filter docs wherever maintenance filters are listed.
- `CHANGELOG.md` under `[Unreleased]`, referencing #85.
- `README.md` if it lists feed parameters or calendar features.

## Testing

Per the project rules, test plugin-owned logic only:

- Filterset: `duration_min` / `duration_max` boundaries (inclusive), fractional
  values, combined min+max.
- iCal view: params parsed, applied, invalid value -> 400, ETag differs with
  and without a duration filter.
- No tests that only round-trip Django/DRF. The JS rendering has no test
  harness in this repo; verify manually in the browser and include
  screenshots in the PR.

## Left to the builder

- The FullCalendar technique for overlapping bands and short events.
- Exact CSS values (heights, opacity, text shade) within the look above.
- How the iCal view shares the duration logic with the filterset.
- Whether `duration` is a queryset annotation or computed inline; note CI
  also runs Django 5.2, where generated fields are not refreshed on UPDATE,
  so avoid a stored generated column.
