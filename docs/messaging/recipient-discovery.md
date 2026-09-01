# Recipient Discovery

Recipient discovery answers one question: given an event and a template, which NetBox contacts should hear about it? The answer is derived from the objects the event impacts, not maintained as a separate mailing list.

The implementation is `notices/services/recipient_discovery.py`.

## The path from event to contact

Discovery walks four hops:

```
Event  ->  Impact  ->  target.tenant  ->  ContactAssignment  ->  Contact
```

1. Collect the event's `Impact` records.
2. For each impact, read `tenant` from the impact's target object.
3. For each distinct tenant, look up its contact assignments.
4. Filter those assignments by the template's roles and priorities, and return the contacts.

Every step is a plain traversal of NetBox's own tenancy data. There is no notification-specific recipient list to keep up to date, which is the point: if a circuit is assigned to the right tenant and the tenant has the right contacts, the notification reaches the right people.

The consequence is that **a target with no tenant produces no recipients**. An impact on a device that has never been assigned a tenant contributes nothing to the recipient list and raises no error. This is the usual reason a notification comes out empty.

The tenant is read from the target object itself, not from the event. A maintenance has no tenant of its own; it inherits its audience from what it impacts.

## Roles and priorities

Two fields on the template narrow the contacts pulled from a tenant.

`contact_roles` is a set of `tenancy.ContactRole` objects. When populated, only assignments with one of those roles are considered. When empty, role is not filtered on at all.

`contact_priorities` is a list of priority values, from `primary`, `secondary` and `tertiary`. When populated, only assignments at those priorities are considered. When empty, priority is not filtered on.

Both fields are permissive when empty, which means a template with neither set collects every contact assigned to every affected tenant. Narrowing usually means setting at least a role.

One filter is always applied regardless of configuration: assignments with priority `inactive` are excluded. There is no way to include them.

Contacts are deduplicated by primary key, so a contact assigned to a tenant twice under different roles appears once.

## Granularity

The template's `granularity` decides how the result is grouped, and the return type changes with it.

| Granularity | Return value |
|---|---|
| `per_event` | A flat list of `Contact` objects |
| `per_tenant` | A dict of `{tenant: [Contact, ...]}` |
| `per_impact` | A dict of `{impact: [Contact, ...]}` |

`per_event` produces one notification for the whole event, addressed to everyone affected. Every tenant sees the full impact list, including impacts belonging to other tenants, so it suits internal distribution rather than customer notices.

`per_tenant` is the default and the usual choice for customer notices. Each tenant gets its own notification, and the `tenant_impacts` context variable is narrowed to that tenant's impacts. See [Templates](templates.md).

`per_impact` produces one notification per impact record. A tenant with six affected circuits receives six notifications. This is for cases where each notice has to name a single service, and it can generate a large volume from one event.

An unrecognised granularity value falls back to `per_event`.

In `per_impact`, an impact whose target has no tenant is still present as a key, mapped to an empty list. In `per_tenant` and `per_event` it is skipped entirely.

## Calling it

The service takes a template and exposes two entry points.

```python
from notices.services.recipient_discovery import RecipientDiscoveryService

service = RecipientDiscoveryService(template)

service.discover_for_event(maintenance)
service.discover_for_event(maintenance, granularity="per_event")
service.discover_for_tenant(tenant)
```

`discover_for_event()` takes an optional `granularity` argument that overrides the template's own, which is useful for previewing what a different grouping would produce.

`discover_for_tenant()` skips the impact traversal and returns the contacts for one tenant directly. It is the path for standalone notifications, which have no event to walk.

A convenience function wraps both:

```python
from notices.services.recipient_discovery import discover_recipients

discover_recipients(template, event=maintenance)
discover_recipients(template, tenant=acme)
discover_recipients(template, event=maintenance, granularity="per_impact")
```

`discover_recipients` prefers `event` when both are supplied, and returns an empty list when neither is.

The service reads `contact_roles` and `contact_priorities` once, in its constructor. Changing the template after building a service has no effect on that instance.

## Discovery is not the snapshot

Discovery produces `Contact` objects. It does not decide what a notification is finally sent to.

Contacts are attached to a `PreparedNotification` through its `contacts` M2M. The list of addresses that delivery actually uses is `recipients`, a JSON snapshot taken by the state machine when the notification moves from `draft` to `ready`:

```json
[
  {"email": "noc@example.com", "name": "Example NOC", "contact_id": 12}
]
```

Two things follow. A contact with no email address is dropped at snapshot time, so it can be attached to a notification and still not receive it. And editing a contact's address after approval does not change where an already-approved notification goes, because the snapshot is what delivery reads. That is deliberate: the record shows where the message was actually addressed.

A notification with an empty snapshot cannot be approved. The transition to `ready` raises a validation error rather than producing a notification with no audience. See [Approval Workflow](workflow.md).

## Troubleshooting an empty list

Work back along the path, in this order:

1. **Does the event have impacts?** No impacts means no targets, so no tenants.
2. **Do the impact targets have a tenant?** This is the most common cause. Check `impact.target.tenant` for each.
3. **Does the tenant have contact assignments?** Look at the Contacts panel on the tenant.
4. **Do the assignments match the template's roles?** An empty `contact_roles` matches everything, so a role set on the template that nobody is assigned under yields nothing.
5. **Do they match the priorities?** Same logic, and remember that `inactive` is always excluded.
6. **Do the contacts have email addresses?** They will survive discovery and disappear at snapshot time.

A quick check in `nbshell`:

```python
from notices.models import Maintenance, NotificationTemplate
from notices.services.recipient_discovery import discover_recipients

m = Maintenance.objects.get(name="PWIC-12345")
t = NotificationTemplate.objects.get(slug="customer-maintenance")

for impact in m.impacts.all():
    print(impact.target, "->", getattr(impact.target, "tenant", None))

discover_recipients(t, event=m)
```

## See also

- [Templates](templates.md) for `contact_roles`, `contact_priorities` and granularity
- [Approval Workflow](workflow.md) for the recipient snapshot
- [Impact Tracking](../events/impact.md) for how impacts are created
