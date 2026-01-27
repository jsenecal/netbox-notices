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

# Messaging group
messaging_items = [
    PluginMenuItem(
        link="plugins:notices:messagetemplate_list",
        link_text="Message Templates",
        permissions=["notices.view_messagetemplate"],
        buttons=[
            PluginMenuButton(
                link="plugins:notices:messagetemplate_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
                permissions=["notices.add_messagetemplate"],
            )
        ],
    ),
    PluginMenuItem(
        link="plugins:notices:preparedmessage_list",
        link_text="Prepared Messages",
        permissions=["notices.view_preparedmessage"],
        buttons=[
            PluginMenuButton(
                link="plugins:notices:preparedmessage_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
                permissions=["notices.add_preparedmessage"],
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
