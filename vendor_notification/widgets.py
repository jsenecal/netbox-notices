from django.db.models import Count
from django.template.loader import render_to_string
from extras.dashboard.utils import register_widget
from extras.dashboard.widgets import DashboardWidget

from .models import Maintenance


@register_widget
class UpcomingMaintenanceWidget(DashboardWidget):
    default_title = "Upcoming Maintenance Events"
    description = "Show a list of upcoming maintenance events"
    template_name = "vendor_notification/widget.html"
    width = 8
    height = 3

    def render(self, request):
        return render_to_string(
            self.template_name,
            {
                "maintenances": Maintenance.objects.filter(
                    status__in=[
                        "TENTATIVE",
                        "CONFIRMED",
                        "IN-PROCESS",
                        "RE-SCHEDULED",
                        "UNKNOWN",
                    ]
                ).annotate(impact_count=Count("impacts")),
            },
        )


# MaintenanceCalendarWidget removed - replaced by full calendar view
# The dashboard widget used the old HTMLCalendar implementation
# which was replaced by FullCalendar.js in the main calendar view.
# Dashboard calendar widget will be reimplemented in a future update.

# @register_widget
# class MaintenanceCalendarWidget(DashboardWidget):
#     default_title = "Upcoming Circuit Maintenance Calendar"
#     description = "Show a simplified calendar view showing upcoming maintenance events this month"
#     template_name = "vendor_notification/calendar_widget.html"
#     width = 8
#     height = 8
#
#     def render(self, request):
#         curr_month = datetime.date.today()
#
#         # Load calendar
#         cal = Calendar()
#         html_calendar = cal.formatmonth(curr_month.year, curr_month.month)
#         html_calendar = html_calendar.replace("<td ", '<td  width="100" height="100"')
#
#         return render_to_string(self.template_name, {"calendar": mark_safe(html_calendar)})
