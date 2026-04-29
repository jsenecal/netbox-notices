# Installation

This page covers installing and enabling the `netbox-notices` plugin in an existing NetBox deployment.

## Requirements

| Component | Required version |
|-----------|------------------|
| NetBox | 4.5.0 or later |
| Python | 3.10, 3.11, 3.12, 3.13, or 3.14 |
| PostgreSQL | Whatever your NetBox version requires |

The plugin module name on disk is `notices` (note: not `netbox_notices`). The PyPI distribution name is `netbox-notices`.

## Install from PyPI

Activate the NetBox virtual environment and install via pip:

```bash
source /opt/netbox/venv/bin/activate
pip install netbox-notices
```

To make the install persist across NetBox upgrades, add the package to your `local_requirements.txt`:

```bash
echo netbox-notices >> /opt/netbox/local_requirements.txt
```

## Enable the plugin

Edit `configuration.py` (typically `/opt/netbox/netbox/netbox/configuration.py`) and add `notices` to the `PLUGINS` list:

```python
PLUGINS = [
    "notices",
]

PLUGINS_CONFIG = {
    "notices": {},
}
```

The empty dict accepts the defaults documented on the [Configuration](configuration.md) page. You almost certainly want to extend `allowed_content_types` to include the model classes you intend to link impacts to (Devices, VirtualMachines, etc).

## Apply database migrations

```bash
cd /opt/netbox
source venv/bin/activate
python netbox/manage.py migrate
```

The plugin's migrations live under `notices/migrations/` and will create the following tables:

- `notices_maintenance`
- `notices_outage`
- `notices_impact` (with M2M tables `notices_impact_sites` and `notices_impact_locations`)
- `notices_eventnotification`
- `notices_notificationtemplate`
- `notices_templatescope`
- `notices_preparednotification` (with `notices_preparednotification_contacts`)

## Restart NetBox

```bash
sudo systemctl restart netbox netbox-rq
```

After restart you should see a new top-level **Notices** menu in the NetBox UI with the **Dashboard**, **Notifications**, **Events**, and **Messaging** groups.

## Verify the install

Hit the API root and confirm the `notices` plugin is listed:

```bash
curl -H "Authorization: Token YOUR_API_TOKEN" \
  https://netbox.example.com/api/plugins/notices/
```

You should see the available endpoints (`maintenance/`, `outage/`, `impact/`, `eventnotification/`, `notification-templates/`, `prepared-notifications/`, `sent-notifications/`).

## Upgrading

To upgrade to a newer release:

```bash
source /opt/netbox/venv/bin/activate
pip install --upgrade netbox-notices
python /opt/netbox/netbox/manage.py migrate
sudo systemctl restart netbox netbox-rq
```

Always read the [Changelog](changelog.md) before upgrading to confirm there are no breaking changes for your configuration.

## Migrating from netbox-circuitmaintenance

There is **no automatic upgrade path** from `jasonyates/netbox-circuitmaintenance`. The data model has changed:

- The `CircuitMaintenance` model is replaced by `Maintenance`.
- `CircuitMaintenanceImpact` (which referenced a Circuit by FK) is replaced by `Impact`, which uses a GenericForeignKey to support any allowed content type.
- A new `Outage` model exists for unplanned events.
- The notification storage model has been renamed to `EventNotification` and also uses a GenericForeignKey.

If you are migrating, export your old maintenance and impact data via the original plugin's REST API and re-import via this plugin's API. See the [REST API](api/rest-api.md) reference for endpoint details.
