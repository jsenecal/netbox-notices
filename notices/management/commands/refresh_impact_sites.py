"""
Rebuild the Impact.sites / Impact.locations cache from scratch.

Useful after:

- Bulk imports / management scripts that bypass signals
- Adding a new resolver and wanting to backfill prior impacts
- Suspected drift (signal handler missing for a custom content type)
"""

from django.core.management.base import BaseCommand

from notices.models import Impact


class Command(BaseCommand):
    help = "Recompute Impact.sites and Impact.locations for every Impact via the resolver registry."

    def add_arguments(self, parser):
        parser.add_argument(
            "--impact-id",
            type=int,
            action="append",
            help="Limit to specific Impact PKs (repeatable). Default: all impacts.",
        )

    def handle(self, *args, **options):
        qs = Impact.objects.all()
        if options.get("impact_id"):
            qs = qs.filter(pk__in=options["impact_id"])

        total = qs.count()
        self.stdout.write(f"Refreshing {total} impact(s)...")
        for i, impact in enumerate(qs.iterator(), start=1):
            impact.refresh_sites()
            if i % 100 == 0:
                self.stdout.write(f"  {i}/{total}")
        self.stdout.write(self.style.SUCCESS(f"Done. Refreshed {total} impact(s)."))
