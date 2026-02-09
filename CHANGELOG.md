# Changelog

## 1.0.0 (2026-02-09)

### New Features

* **Outgoing Notifications**: New notification system for customer/stakeholder communication
  * NotificationTemplate model with Jinja templating support
  * Template scoping (similar to Config Contexts) for tenant/provider/site-specific templates
  * Template inheritance for customization
  * PreparedNotification model with approval workflow (draft → ready → sent → delivered/failed)
  * SentNotification proxy model for viewing sent/delivered notifications
  * Recipient discovery based on contact roles and priorities
  * iCal attachment support for maintenance notifications
* **AWS SES Integration** (`integrations/aws-ses/`): Complete AWS SAM application for email delivery
  * **Inbound Lambda** — SES receipt rule → S3 → parse with circuit-maintenance-parser → NetBox API
  * **Outbound Lambda** — Poll NetBox for ready notifications → build MIME → send via SES
  * **Tracking Lambda** — SES delivery events (delivery, bounce, complaint, open, click) via SNS → NetBox status updates
  * Webhook support via API Gateway for immediate delivery on status change (alternative to polling)
  * Polling and webhook modes independently toggleable (can use either or both)
  * Optional VPC deployment for Lambda functions (private subnets with NAT Gateway)
  * SES Configuration Set with full event tracking (send, delivery, bounce, complaint, open, click)
  * HMAC-SHA512 webhook signature verification for NetBox Event Rules
  * Comprehensive documentation: architecture, quick start, email authentication (SPF, DKIM, DMARC)
* **Developer Tooling**: Plugin demo data loader and netbox-demo-data toolkit integration

### API Changes

* New endpoints for notification management:
  * `/api/plugins/notices/notification-templates/` - CRUD for notification templates
  * `/api/plugins/notices/prepared-notifications/` - CRUD with status workflow
  * `/api/plugins/notices/sent-notifications/` - Read-only view of sent notifications
* Status transitions support optional `timestamp` and `message` fields

### UI Changes

* Renamed "Inbound" menu item to "Received" for clarity
* New "Sent" menu item for viewing sent/delivered notifications
* New "Notification Templates" management UI
* New "Prepared Notifications" management UI with approval workflow

### Documentation

* AWS SES integration guide with architecture diagrams and deployment instructions
* Outgoing notifications documentation with Slack and SES integration examples
* Email authentication guide (SPF, DKIM, DMARC, Custom MAIL FROM)
* Updated parsers documentation with SES cross-references

---

## 0.1.0 (2025-11-18)

**BREAKING CHANGE**: Complete refactor from netbox-circuitmaintenance to netbox-notices

This is the initial release of the fully refactored plugin, now supporting both maintenance and outage tracking across multiple NetBox object types.

### New Features

* **Outage Tracking**: New Outage model for unplanned outages with automatic timestamps
* **Generic Impact Tracking**: Associate impacts with any NetBox object (circuits, devices, VMs, etc.)
* **Reschedule Functionality**: Reschedule maintenance events with automatic status updates
* **Timeline View**: Visual timeline of all changes and events
* **Choice Constants**: All ChoiceSet classes now define constants (STATUS_*, IMPACT_*)
* **Impact Field**: Added impact text field to BaseEvent for describing event impact
* **Reported At**: Outage model includes reported_at timestamp with timezone conversion
* **Timezone Support**: Automatic timezone conversion and display for all timestamp fields
* **Changelog Tracking**: Proper changelog tracking for reschedule operations and related objects
* **PyPI Publishing**: Automated GitHub Actions workflow for PyPI releases

### API Changes

* REST API support for Maintenance and Outage models
* API serializers include all new fields (impact, reported_at, replaces)

### Infrastructure

* NetBox 4.4.1+ compatibility
* Python 3.10+ required
* Automated CI/CD with GitHub Actions
* MkDocs documentation with GitHub Pages deployment

### Migration Notes

This is a completely new plugin architecture. Previous versions (0.6.0 and earlier as netbox-circuitmaintenance) are not compatible.

---

## Historical Releases (netbox-circuitmaintenance)

## 0.6.0 (2025-09-08)

* Netbox 4.4 support
* Bug fix by @PetrVoronov
* Highlight current date in calendar event view

## 0.5.0 (2025-06-02)

* Netbox 4.2 support

## 0.4.2 (2024-09-29)

* Adding Maintenance calendar widget
* Fix #26 - f string quote issue with NB 4.1

## 0.4.1 (2024-09-19)

* Adding Maintenance Schedule calendar


## 0.4.0 (2024-09-19)

* Adds support for Netbox 4.0 and 4.1
* Adds widget to show circuit maintenance events
* Updates styling to match new Netbox style


## 0.3.0 (2023-04-28)

* Fixed support for Netbox 3.5. NOTE: Plugin version 0.3.0+ is only compatible with Netbox 3.5+

## 0.2.2 (2023-01-18)

* Fix API Filtersets
* Viewing notification content opens a new tab
* Updating RESCHEDULED to RE-SCHEDULED to match circuitparser

## 0.2.1 (2023-01-17)

* Updating to DynamicModelChoiceField
* Hiding maintenance schedule for now

## 0.1.0 (2023-01-15)

* First release on PyPI.


