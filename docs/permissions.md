# Permissions

The plugin defines standard Django permissions for each model: `add`, `change`, `delete`, and `view`. Permissions are namespaced under `notices.<perm>_<model>`.

## Permission reference

| Permission | Required to |
|------------|-------------|
| `notices.view_maintenance` | View Maintenance list, detail, dashboard, calendar, iCal feed |
| `notices.add_maintenance` | Create Maintenance events |
| `notices.change_maintenance` | Edit Maintenance events; use the Acknowledge / Mark in Progress / Mark Completed / Cancel / Reschedule quick actions |
| `notices.delete_maintenance` | Delete Maintenance events |
| `notices.view_outage` | View Outage list and detail |
| `notices.add_outage` | Create Outage events |
| `notices.change_outage` | Edit Outage events |
| `notices.delete_outage` | Delete Outage events |
| `notices.view_impact` | View Impact records (no dedicated list view; viewed through events) |
| `notices.add_impact` | Add an Impact, linking an event to a target object |
| `notices.change_impact` | Edit an Impact |
| `notices.delete_impact` | Remove an Impact |
| `notices.view_eventnotification` | View received provider notifications |
| `notices.add_eventnotification` | Upload a new EventNotification (typically done via the API by a parser) |
| `notices.delete_eventnotification` | Delete an EventNotification |
| `notices.view_notificationtemplate` | View NotificationTemplates |
| `notices.add_notificationtemplate` | Create new NotificationTemplates |
| `notices.change_notificationtemplate` | Edit NotificationTemplates and their TemplateScopes |
| `notices.delete_notificationtemplate` | Delete NotificationTemplates |
| `notices.view_preparednotification` | View PreparedNotifications and the Sent Notifications proxy list |
| `notices.add_preparednotification` | Create PreparedNotifications |
| `notices.change_preparednotification` | Edit PreparedNotifications and transition status (e.g. mark as ready, sent, delivered, failed) |
| `notices.delete_preparednotification` | Delete PreparedNotifications |

The `SentNotification` proxy model uses the same `view_preparednotification` permission rather than introducing its own.

## Recommended role bindings

| Role | Suggested permissions |
|------|------------------------|
| **NOC operator** (handles live events) | `view_*`, `change_maintenance`, `change_outage`, `add_impact`, `change_impact` |
| **NOC supervisor** (full event lifecycle) | All of the above plus `add_maintenance`, `add_outage`, `delete_*` for events |
| **Notification approver** | `view_preparednotification`, `change_preparednotification` (so they can transition `draft` -> `ready`) |
| **External delivery service** (API token) | `view_preparednotification`, `change_preparednotification` (to mark `ready` -> `sent` -> `delivered/failed`); `add_eventnotification` if it also stores received emails |
| **Provider parser** (API token) | `add_maintenance`, `add_outage`, `add_impact`, `add_eventnotification`, `change_maintenance`, `change_outage` |
| **Read-only auditor** | All `view_*` permissions |

## Object-level permissions

The plugin uses NetBox's standard `RestrictedQuerySet` patterns, so NetBox's object-level permission constraints (filter by JSON expression) work for every model. For example, restrict a parser token to a specific Provider:

```json
{ "provider": 7 }
```

attached to a `notices.add_maintenance` permission with `users` set to the parser user limits that token to creating Maintenance events for provider 7 only.

## API tokens for the iCal feed

The iCal feed (`/api/plugins/notices/ical/`) accepts three authentication modes (in order):

1. `?token=<plaintext>` URL parameter (works with both v1 and v2 NetBox tokens; v2 tokens have the `nbt_<key>.<plaintext>` form).
2. `Authorization: Token <plaintext>` HTTP header.
3. Browser session cookie (when subscribing from a logged-in browser).

If `LOGIN_REQUIRED = False` is set in NetBox configuration, anonymous access is also accepted.

The feed checks `notices.view_maintenance` on the resolved user. Token-based access is the recommended way to subscribe a calendar app -- generate a per-user token in NetBox under **Profile -> API Tokens** and append it to the subscribe URL.

See the [Calendar and iCal Feed](events/calendar-and-ical.md) page for the URL format and query parameters.
