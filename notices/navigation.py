from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

# Notifications group
notifications_items = [
    PluginMenuItem(
        link="plugins:notices:eventnotification_list",
        link_text="Inbound",
        permissions=["notices.view_eventnotification"],
        buttons=[
            PluginMenuButton(
                link="plugins:notices:eventnotification_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
                permissions=["notices.add_eventnotification"],
            )
        ],
    ),
]

# Events group
events_items = [
    PluginMenuItem(
        link="plugins:notices:maintenance_list",
        link_text="Planned Maintenances",
        permissions=["notices.view_maintenance"],
        buttons=[
            PluginMenuButton(
                link="plugins:notices:maintenance_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
                permissions=["notices.add_maintenance"],
            )
        ],
    ),
    PluginMenuItem(
        link="plugins:notices:outage_list",
        link_text="Outages",
        permissions=["notices.view_outage"],
        buttons=[
            PluginMenuButton(
                link="plugins:notices:outage_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
                permissions=["notices.add_outage"],
            )
        ],
    ),
    PluginMenuItem(
        link="plugins:notices:maintenance_calendar",
        link_text="Calendar",
        permissions=["notices.view_maintenance"],
    ),
]

menu = PluginMenu(
    label="Notices",
    groups=(
        ("Notifications", notifications_items),
        ("Events", events_items),
    ),
    icon_class="mdi mdi-wrench",
)
