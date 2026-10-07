"""Tests for opt-in automatic notification generation."""

import datetime
from unittest import mock

import pytest
from django.db import transaction

from notices import auto_generation
from notices.models import Impact, PreparedNotification

SETTING = "notices.auto_generation.auto_statuses"


@pytest.fixture
def kind(make_template):
    return make_template("noc", name="NOC", subject_template="S {{ maintenance.status }}")


@pytest.mark.django_db
class TestAutoGeneration:
    def test_off_by_default(self, maintenance_with_two_tenants, kind, django_capture_on_commit_callbacks):
        event, *_ = maintenance_with_two_tenants
        with django_capture_on_commit_callbacks(execute=True):
            event.snapshot()
            event.status = "TENTATIVE"
            event.save()
        assert PreparedNotification.objects.count() == 0

    def test_status_change_into_configured_status_generates(
        self, maintenance_with_two_tenants, kind, django_capture_on_commit_callbacks
    ):
        event, *_ = maintenance_with_two_tenants
        with mock.patch(SETTING, return_value=["CANCELLED"]), django_capture_on_commit_callbacks(execute=True):
            event.snapshot()
            event.status = "CANCELLED"
            event.save()
        assert PreparedNotification.objects.get().subject == "S CANCELLED"

    def test_trivial_change_does_not_generate(
        self, maintenance_with_two_tenants, kind, django_capture_on_commit_callbacks
    ):
        event, *_ = maintenance_with_two_tenants
        with mock.patch(SETTING, return_value=["CONFIRMED"]), django_capture_on_commit_callbacks(execute=True):
            event.snapshot()
            event.comments = "note"
            event.save()
        assert PreparedNotification.objects.count() == 0

    def test_one_run_per_transaction(
        self, maintenance_with_two_tenants, kind, site, django_capture_on_commit_callbacks
    ):
        event, *_ = maintenance_with_two_tenants
        with (
            mock.patch(SETTING, return_value=["CONFIRMED"]),
            mock.patch.object(auto_generation, "run_generation", wraps=auto_generation.run_generation) as run,
            django_capture_on_commit_callbacks(execute=True),
        ):
            with transaction.atomic():
                event.snapshot()
                event.end = event.end + datetime.timedelta(hours=1)
                event.save()
                Impact.objects.create(event=event, target=site, impact="DEGRADED")
        assert run.call_count == 1

    def test_unrun_callback_does_not_suppress_later_scheduling(
        self, maintenance_with_two_tenants, kind, django_capture_on_commit_callbacks
    ):
        """A queued-but-never-executed callback (rolled back or captured only) must not leak."""
        event, *_ = maintenance_with_two_tenants
        with mock.patch(SETTING, return_value=["CONFIRMED"]):
            with django_capture_on_commit_callbacks(execute=False):
                auto_generation.schedule_generation(event)
            auto_generation.connections["default"].run_on_commit.clear()
            with django_capture_on_commit_callbacks(execute=False) as callbacks:
                auto_generation.schedule_generation(event)
        assert len(callbacks) == 1

    def test_failure_is_journaled_and_does_not_break_save(
        self, maintenance_with_two_tenants, kind, django_capture_on_commit_callbacks
    ):
        from extras.models import JournalEntry

        event, *_ = maintenance_with_two_tenants
        kind.body_template = "{% if %}"
        kind.save()
        with mock.patch(SETTING, return_value=["CANCELLED"]), django_capture_on_commit_callbacks(execute=True):
            event.snapshot()
            event.status = "CANCELLED"
            event.save()
        assert JournalEntry.objects.filter(assigned_object_id=event.pk, kind="warning").exists()

    def test_status_gate_is_checked_when_the_run_starts(
        self, maintenance_with_two_tenants, kind, django_capture_on_commit_callbacks
    ):
        event, *_ = maintenance_with_two_tenants
        with mock.patch(SETTING, return_value=["CANCELLED"]), django_capture_on_commit_callbacks(execute=True):
            event.snapshot()
            event.start = event.start - datetime.timedelta(hours=1)
            event.save()
        assert event.status == "CONFIRMED"
        assert PreparedNotification.objects.count() == 0

    def test_change_detection_skipped_when_auto_mode_is_off(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        with mock.patch.object(auto_generation, "is_meaningful_event_change") as meaningful:
            event.save()
        meaningful.assert_not_called()

    @pytest.mark.parametrize("setting", [["CONFIRMED"], "CONFIRMED", {"maintenance": "CONFIRMED"}])
    def test_malformed_setting_does_not_break_save(
        self, maintenance_with_two_tenants, kind, setting, django_capture_on_commit_callbacks
    ):
        event, *_ = maintenance_with_two_tenants
        config = mock.Mock(PLUGINS_CONFIG={"notices": {"auto_generate_notifications": setting}})
        with (
            mock.patch("notices.auto_generation.get_config", return_value=config),
            django_capture_on_commit_callbacks(execute=True),
        ):
            event.save()
        assert PreparedNotification.objects.count() == 0

    def test_callback_failure_does_not_escape(
        self, maintenance_with_two_tenants, kind, django_capture_on_commit_callbacks
    ):
        event, *_ = maintenance_with_two_tenants
        with (
            mock.patch(SETTING, return_value=["CANCELLED"]),
            mock.patch.object(auto_generation, "run_generation", side_effect=RuntimeError("boom")),
            django_capture_on_commit_callbacks(execute=True),
        ):
            event.snapshot()
            event.status = "CANCELLED"
            event.save()
        assert PreparedNotification.objects.count() == 0
