from netbox.choices import ButtonColorChoices
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
                color=ButtonColorChoices.GREEN,
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
                color=ButtonColorChoices.GREEN,
            )
        ],
    ),
    PluginMenuItem(
        link="plugins:vendor_notification:maintenanceschedule",
        link_text="Maintenance Schedule",
    ),
]

menu = PluginMenu(
    label="Vendor Notification",
    groups=(("Vendor Notification", menuitems),),
    icon_class="mdi mdi-wrench",
)
