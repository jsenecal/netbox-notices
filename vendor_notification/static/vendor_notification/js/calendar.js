// Initialize FullCalendar when page loads
document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');

    const calendar = new FullCalendar.Calendar(calendarEl, {
        // Basic settings
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,dayGridWeek'
        },

        // Event data source - FullCalendar handles the API calls automatically
        events: {
            url: '/api/plugins/vendor-notification/maintenance/',
            extraParams: function(fetchInfo) {
                return {
                    // Use NetBox's built-in operators for date range filtering
                    end__gte: fetchInfo.startStr.split('T')[0],    // Events ending on or after range start
                    start__lte: fetchInfo.endStr.split('T')[0],    // Events starting on or before range end
                    limit: 0  // No pagination, get all events in range
                };
            },
            success: function(data) {
                // Transform NetBox API response to FullCalendar event format
                return data.results.map(event => ({
                    id: event.id,
                    title: `${event.name} - ${event.provider.display}`,
                    start: event.start,
                    end: event.end,
                    backgroundColor: `var(--tblr-${event.status_color})`,  // Use Tabler CSS variables
                    borderColor: `var(--tblr-${event.status_color})`,
                    extendedProps: {
                        status: event.status,
                        provider: event.provider.display,
                        summary: event.summary,
                        comments: event.comments,
                        url: event.url
                    }
                }));
            }
        },

        // Click handler - opens modal instead of navigating
        eventClick: function(info) {
            info.jsEvent.preventDefault(); // Don't follow URL
            showEventModal(info.event);
        },

        // Display multi-day events properly
        displayEventTime: true,
        displayEventEnd: true
    });

    calendar.render();
});

// Show event details in Bootstrap modal
function showEventModal(event) {
    const modal = new bootstrap.Modal(document.getElementById('eventModal'));

    // Populate modal fields
    document.getElementById('eventModalTitle').textContent = event.title;
    document.getElementById('eventModalProvider').textContent = event.extendedProps.provider;
    document.getElementById('eventModalSummary').textContent = event.extendedProps.summary;

    // Format dates
    document.getElementById('eventModalStart').textContent =
        new Date(event.start).toLocaleString();
    document.getElementById('eventModalEnd').textContent =
        new Date(event.end).toLocaleString();

    // Status badge with color from backend
    const statusBadge = document.getElementById('eventModalStatus');
    statusBadge.textContent = event.extendedProps.status;
    statusBadge.className = `badge bg-${event.backgroundColor.replace('var(--tblr-', '').replace(')', '')}`;

    // Comments (optional field)
    const commentsRow = document.getElementById('eventModalCommentsRow');
    if (event.extendedProps.comments) {
        document.getElementById('eventModalComments').textContent = event.extendedProps.comments;
        commentsRow.style.display = 'flex';
    } else {
        commentsRow.style.display = 'none';
    }

    // Link to full detail page
    document.getElementById('eventModalViewLink').href = event.extendedProps.url;

    modal.show();
}
