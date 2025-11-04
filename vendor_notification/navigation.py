from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

menuitems = [
    PluginMenuItem(
        link="plugins:vendor_notification:maintenance_list",
        link_text="Maintenance Events",
        buttons=[
            PluginMenuButton(
                link="plugins:vendor_notification:maintenance_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
            )
        ],
    ),
    PluginMenuItem(
        link="plugins:vendor_notification:outage_list",
        link_text="Outages",
        buttons=[
            PluginMenuButton(
                link="plugins:vendor_notification:outage_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
            )
        ],
    ),
    PluginMenuItem(
        link="plugins:vendor_notification:maintenanceschedule",
        link_text="Maintenance Schedule",
    ),
]

menu = PluginMenu(
    label="Vendor Notifications",
    groups=(("Notifications", menuitems),),
    icon_class="mdi mdi-wrench",
)
