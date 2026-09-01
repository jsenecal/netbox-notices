# Dashboard

The dashboard is the landing page of the plugin, at `/plugins/notices/`, reachable from **Notices > Dashboard > Summary**. It answers the question a NOC asks at the start of a shift: what is happening now, what is coming, and what has nobody looked at yet.

It is a read-only summary. Every figure and row links through to the underlying record or list.

## Access

The whole page requires a single permission, `notices.view_maintenance`. The outage counters are rendered without a separate `notices.view_outage` check, so a user who can see the dashboard sees outage figures whether or not they can open the outage records themselves.

Unlike the model list views, the dashboard does not apply object-level permission filtering. Its queries count every matching row. On a deployment that uses constrained permissions to partition events between teams, the counters are deployment-wide rather than scoped to the viewer.

## What counts as active

Two status groups drive most of the page.

| Group | Statuses |
|---|---|
| Active maintenance | `TENTATIVE`, `CONFIRMED`, `IN-PROCESS`, `RE-SCHEDULED` |
| Active outage | `REPORTED`, `INVESTIGATING`, `IDENTIFIED`, `MONITORING` |

`COMPLETED`, `CANCELLED` and `RESOLVED` are terminal and never counted as active. Note that `RE-SCHEDULED` counts as active: a maintenance that has been superseded still appears in the totals until it is closed out, alongside the replacement that superseded it.

## Statistics

Six counters sit at the top of the page.

| Counter | Query |
|---|---|
| Maintenance in progress | Maintenances with status `IN-PROCESS`. No date bound. |
| Active outages | Outages in any active status. No date bound. |
| Confirmed this week | Maintenances with status `CONFIRMED` starting between now and seven days from now. |
| Upcoming (7 days) | Maintenances in any active status starting in the next seven days. |
| Upcoming (30 days) | Maintenances in any active status starting in the next thirty days. |
| Unacknowledged | Active maintenances plus active outages where `acknowledged` is false. |

A tile is only rendered when its value is non-zero, so a quiet week shows a shorter page rather than a row of zeros.

Two details are worth knowing when the numbers look wrong. "Confirmed this week" is a subset of "Upcoming (7 days)" rather than a separate group, since `CONFIRMED` is one of the active statuses. And both upcoming counters filter on `start` only, so a long maintenance that began last week and runs through next week is counted in neither.

The unacknowledged counter is the one to watch. `acknowledged` is set from the **Acknowledge** quick action on a maintenance, and nothing sets it automatically, so this figure is the backlog of events that arrived and were never reviewed.

## Timeline

Below the counters is a fourteen-day timeline, built from two queries.

Maintenances appear if they are in an active status, start before the end of the window, and have not already ended. That last condition means the timeline shows events currently in flight, not only those that have yet to begin. Results are ordered by start time and capped at twenty.

Outages appear if they are in an active status, with no date filter at all. An outage that has been open for three months is still shown, which is deliberate: an unresolved outage is current regardless of when it started. Results are ordered by start time and capped at twenty.

Both querysets select the provider and annotate an impact count, so the timeline renders without per-row queries.

The twenty-row cap is fixed and there is no pagination. When either list is truncated the page gives no indication, so treat a timeline holding exactly twenty rows as a prompt to use the [maintenance](maintenance.md) or [outage](outage.md) list views instead.

## Upcoming by provider

The last section groups scheduled work by provider. It selects maintenances with status `TENTATIVE` or `CONFIRMED` starting at any point in the future, ordered by provider name and then start time, capped at fifty.

The status filter here is narrower than the one used for the counters: `IN-PROCESS` and `RE-SCHEDULED` are excluded. The section is about work still to be scheduled around, not work already under way.

There is no end date bound, so this list runs as far into the future as your records go.

## Filtering and export

The dashboard has neither. It runs a fixed set of queries with no query-parameter handling, and offers no CSV or bulk actions.

For anything beyond the summary, use the list views, which carry the full filtersets including the site, region, site group and location filters described in [Impact Tracking](impact.md):

- `/plugins/notices/maintenance/`
- `/plugins/notices/outages/`

For a calendar rather than a list, see [Calendar and iCal Feed](calendar-and-ical.md). For the same figures on the NetBox home page, add the **Upcoming Maintenance Events** widget described in [Template Extensions](../developer/template-extensions.md).

## See also

- [Maintenance Events](maintenance.md)
- [Outage Events](outage.md)
- [Permissions](../permissions.md)
