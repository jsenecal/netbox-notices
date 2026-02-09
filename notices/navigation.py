from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

# Notifications group
notifications_items = [
    PluginMenuItem(
        link="plugins:notices:eventnotification_list",
        link_text="Received",
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
    PluginMenuItem(
        link="plugins:notices:sentnotification_list",
        link_text="Sent",
        permissions=["notices.view_preparednotification"],
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

# Messaging group
messaging_items = [
    PluginMenuItem(
        link="plugins:notices:notificationtemplate_list",
        link_text="Notification Templates",
        permissions=["notices.view_notificationtemplate"],
        buttons=[
            PluginMenuButton(
                link="plugins:notices:notificationtemplate_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
                permissions=["notices.add_notificationtemplate"],
            )
        ],
    ),
    PluginMenuItem(
        link="plugins:notices:preparednotification_list",
        link_text="Prepared Notifications",
        permissions=["notices.view_preparednotification"],
        buttons=[
            PluginMenuButton(
                link="plugins:notices:preparednotification_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
                permissions=["notices.add_preparednotification"],
            )
        ],
    ),
]

menu = PluginMenu(
    label="Notices",
    groups=(
        ("Notifications", notifications_items),
        ("Events", events_items),
        ("Messaging", messaging_items),
    ),
    icon_class="mdi mdi-wrench",
)
