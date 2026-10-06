# Outgoing Notification Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn any Maintenance/Outage into rendered draft `PreparedNotification`s (UI button, REST action, opt-in auto mode), with reset-to-template, approve-from-UI, and timeline visibility.

**Architecture:** Template selection becomes "kinds + overrides along `extends`" in `template_matching.py`; `TemplateRenderer` learns chain-aware Jinja inheritance and body formats; `recipient_discovery.py` exposes impact grouping; a new `NotificationGenerator` service plans (side-effect free) and applies (transactional) generation; views, API actions and signals are thin callers. Postgres computes `content_hash` as a stored generated column; `rendered_hash` is a snapshot copied in SQL.

**Tech Stack:** NetBox 4.5+ plugin, Django 6.1, PostgreSQL 17, Jinja2, DRF, pytest + pytest-django, ruff.

**Spec:** `docs/superpowers/specs/2026-10-06-notification-generation-design.md` -- read it before starting any task.

## Global Constraints

- Work only in the worktree `/opt/netbox-plugins/plugins/netbox-notices/.claude/worktrees/feat+notification-generation` on branch `feat/notification-generation`. Never touch the main checkout.
- Run tests ONLY as `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider <paths> -q` from the worktree root. `python -m` is mandatory: plain `pytest` imports the main checkout's `notices` (editable install at `/opt/plugins/netbox-notices`). Never run db tests unlocked or in the background.
- Lint: `/opt/netbox/venv/bin/ruff check --fix notices/ tests/` and `/opt/netbox/venv/bin/ruff format notices/ tests/` before each commit.
- ASCII-only in all code, comments, docs, templates and commit messages (no em/en dashes, smart quotes, arrows, ellipsis glyphs). Existing non-ASCII you did not write may stay.
- No issue numbers (`#123`) in source comments/docstrings (test docstrings may).
- Tests exercise plugin-owned logic only. No "page returns 200" / "ORM round-trips a field" tests.
- Cleanup is part of the change: delete code and tests made dead by your task.
- Conventional Commits, <= 72 char subject, no AI attribution, never `--no-verify`. Commit at the end of each task on this branch (skill-driven commits are allowed here).
- Migrations: `cd /opt/netbox/netbox && /opt/netbox/venv/bin/python manage.py makemigrations notices` will write into the MAIN checkout (editable install). Instead write the migration file by hand in the worktree's `notices/migrations/` (Task 4 gives it in full).
- Granularity values: `per_event`, `per_tenant`, `per_impact`. Status values: drafts `draft`; past-draft `ready`, `sent`, `delivered`, `failed`.

## Review Focus

1. Rendered subject longer than 255 chars -- must be truncated to 255, not crash the DB insert (Task 5 test).
2. A template body that `{% extends "base" %}` while being itself the parent of another template (three-level chain) -- each level's "base" must resolve to its own parent, never to itself (Task 2 test).
3. Operator generates with a subset of kinds selected -- untouched drafts of UNselected kinds must not be deleted (Task 5 test).
4. Impact whose target has no `tenant` attribute (e.g. a Site) under `per_tenant` -- silently not grouped, no crash; under `per_event` its tenant-less impact still counts in `impacts` context (Task 3 test).
5. Auto mode on an event saved several times in one transaction (event + impacts in one request) -- exactly one generation run after commit (Task 9 test).

---

### Task 1: Kinds-and-overrides template matching

**Files:**
- Modify: `notices/services/template_matching.py`
- Modify: `notices/models/messaging.py` (add `NotificationTemplate.clean()`, `root_kind`, `is_override`)
- Test: `tests/test_template_matching.py` (rewrite the merge-everything / find_templates parts)
- Test: `tests/test_messaging_models.py` (clean() tests)

**Interfaces:**
- Produces (used by Tasks 5, 7, 8):
  - `NotificationTemplate.is_override -> bool` property: `self.extends_id is not None and not self.extends.is_base_template`.
  - `NotificationTemplate.root_kind -> NotificationTemplate` property: walk `extends` while `is_override`; returns the first template that is not an override.
  - `TemplateMatchingService(event=None, tenant=None, provider=None)` (unchanged constructor) with new public method `score(template) -> int | None` (None = template does not apply to this context).
  - `kinds_for_event(event) -> QuerySet[NotificationTemplate]`: non-base, non-override templates whose `event_type` matches the event (`maintenance`/`outage` or `both`), prefetching `scopes__content_type`, `contact_roles`, `children`.
  - `resolve_chain(root, matcher) -> list[NotificationTemplate]`: most specific first: `[winning override, ..., root, base ancestors of root...]`.
  - `merge_templates(chain) -> dict | None`: unchanged algorithm (first non-empty wins, headers key-merge, roles/priorities union, include_ical OR) but WITHOUT the `extends` key, and with `granularity` taken from the LAST non-base entry of the chain (the root kind).
- Removed (dead after this task, delete with their tests): `TemplateMatchingService.find_templates`, `get_best_template`, `get_merged_config`, `_get_candidates_by_event_type`, `find_matching_templates`.

- [ ] **Step 1: Write failing tests** -- add to `tests/test_template_matching.py` (keep existing fixtures; reuse `maintenance`, `tenant`, `tenant_secondary`, `provider` fixtures). Delete test classes `TestFindMatchingTemplates`, `TestGetBestTemplate`, `TestGetMergedConfig`, `TestTemplateInheritance`, `TestGlobalTemplates`, and rewrite `TestEventTypeFiltering` / `TestScopeMatching` / `TestEventStatusFiltering` / `TestScoreCalculation` / `TestEventProviderResolution` assertions to call `kinds_for_event(...)` and `TemplateMatchingService(...).score(template)` instead of `find_templates()`. New tests:

```python
from notices.services.template_matching import (
    TemplateMatchingService,
    kinds_for_event,
    merge_templates,
    resolve_chain,
)


def _tpl(slug, **kw):
    defaults = dict(
        name=slug, slug=slug, event_type="maintenance", granularity="per_tenant",
        subject_template="", body_template="", weight=1000,
    )
    defaults.update(kw)
    return NotificationTemplate.objects.create(**defaults)


def _scope(template, obj, weight=1000, **kw):
    return TemplateScope.objects.create(
        template=template,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        weight=weight,
        **kw,
    )


@pytest.mark.django_db
class TestKinds:
    def test_base_templates_and_overrides_are_not_kinds(self, maintenance):
        base = _tpl("layout", is_base_template=True)
        kind = _tpl("customer", extends=base)
        _tpl("customer-acme", extends=kind)
        _tpl("outage-only", event_type="outage")
        both = _tpl("both", event_type="both")
        assert set(kinds_for_event(maintenance)) == {kind, both}


@pytest.mark.django_db
class TestScore:
    def test_unscoped_template_applies_with_base_weight(self, maintenance):
        t = _tpl("t", weight=10)
        assert TemplateMatchingService(event=maintenance).score(t) == 10

    def test_tenant_scope_applies_only_to_that_tenant(self, maintenance, tenant, tenant_secondary):
        t = _tpl("t", weight=10)
        _scope(t, tenant, weight=5)
        assert TemplateMatchingService(event=maintenance, tenant=tenant).score(t) == 15
        assert TemplateMatchingService(event=maintenance, tenant=tenant_secondary).score(t) is None
        assert TemplateMatchingService(event=maintenance).score(t) is None


@pytest.mark.django_db
class TestResolveChain:
    def test_matching_override_wins_over_root(self, maintenance, tenant):
        root = _tpl("root")
        acme = _tpl("acme", extends=root)
        _scope(acme, tenant)
        matcher = TemplateMatchingService(event=maintenance, tenant=tenant)
        assert resolve_chain(root, matcher) == [acme, root]

    def test_non_matching_override_is_ignored(self, maintenance, tenant, tenant_secondary):
        root = _tpl("root")
        acme = _tpl("acme", extends=root)
        _scope(acme, tenant)
        matcher = TemplateMatchingService(event=maintenance, tenant=tenant_secondary)
        assert resolve_chain(root, matcher) == [root]

    def test_highest_scoring_override_wins(self, maintenance, tenant):
        root = _tpl("root")
        low = _tpl("low", extends=root, weight=1)
        high = _tpl("high", extends=root, weight=2000)
        _scope(low, tenant)
        _scope(high, tenant)
        matcher = TemplateMatchingService(event=maintenance, tenant=tenant)
        assert resolve_chain(root, matcher)[0] == high

    def test_base_ancestors_are_appended(self, maintenance):
        layout = _tpl("layout", is_base_template=True)
        root = _tpl("root", extends=layout)
        assert resolve_chain(root, TemplateMatchingService(event=maintenance)) == [root, layout]

    def test_nested_overrides(self, maintenance, tenant):
        root = _tpl("root")
        mid = _tpl("mid", extends=root)
        leaf = _tpl("leaf", extends=mid)
        _scope(leaf, tenant)
        matcher = TemplateMatchingService(event=maintenance, tenant=tenant)
        assert resolve_chain(root, matcher) == [leaf, mid, root]


@pytest.mark.django_db
class TestChainMerge:
    def test_empty_fields_fall_back_to_parent(self):
        root = _tpl("root", subject_template="S-root", body_template="B-root", css_template="c")
        acme = _tpl("acme", extends=root, subject_template="S-acme")
        merged = merge_templates([acme, root])
        assert merged["subject_template"] == "S-acme"
        assert merged["body_template"] == "B-root"
        assert merged["css_template"] == "c"
        assert merged["granularity"] == "per_tenant"
        assert "extends" not in merged
```

In `tests/test_messaging_models.py` add:

```python
@pytest.mark.django_db
class TestNotificationTemplateClean:
    def _tpl(self, slug, **kw):
        return NotificationTemplate.objects.create(
            name=slug, slug=slug, event_type="maintenance", subject_template="s", body_template="b", **kw
        )

    def test_self_extends_rejected(self):
        t = self._tpl("a")
        t.extends = t
        with pytest.raises(ValidationError, match="cycle"):
            t.clean()

    def test_two_template_cycle_rejected(self):
        a = self._tpl("a")
        b = self._tpl("b", extends=a)
        a.extends = b
        with pytest.raises(ValidationError, match="cycle"):
            a.clean()

    def test_override_granularity_must_match_parent(self):
        parent = self._tpl("p", granularity="per_tenant")
        child = NotificationTemplate(
            name="c", slug="c", event_type="maintenance", subject_template="s", body_template="b",
            extends=parent, granularity="per_event",
        )
        with pytest.raises(ValidationError, match="granularity"):
            child.clean()

    def test_child_of_base_template_may_use_any_granularity(self):
        base = self._tpl("base", is_base_template=True, granularity="per_tenant")
        child = NotificationTemplate(
            name="c", slug="c", event_type="maintenance", subject_template="s", body_template="b",
            extends=base, granularity="per_event",
        )
        child.clean()

    def test_root_kind_walks_overrides_only(self):
        base = self._tpl("base", is_base_template=True)
        root = self._tpl("root", extends=base)
        mid = self._tpl("mid", extends=root)
        leaf = self._tpl("leaf", extends=mid)
        assert leaf.root_kind == root
        assert root.root_kind == root
        assert leaf.is_override and not root.is_override
```

(Import `ValidationError` from `django.core.exceptions` if not already.)

- [ ] **Step 2: Run to confirm failure**

Run: `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/test_template_matching.py tests/test_messaging_models.py -q`
Expected: ImportError for `kinds_for_event` / `resolve_chain`, AttributeError for `root_kind`. Then the new tests fail on assertions once imports exist.

- [ ] **Step 3: Implement model helpers** in `notices/models/messaging.py` inside `NotificationTemplate` (add `from django.core.exceptions import ValidationError` at top):

```python
    @property
    def is_override(self):
        """True when this template overrides a non-base parent for matching recipient groups."""
        return self.extends_id is not None and not self.extends.is_base_template

    @property
    def root_kind(self):
        """The independent notification kind this template belongs to (itself unless it is an override)."""
        template = self
        while template.is_override:
            template = template.extends
        return template

    def clean(self):
        super().clean()
        seen = {self.pk} if self.pk else set()
        parent = self.extends
        while parent is not None:
            if parent.pk in seen or parent is self:
                raise ValidationError({"extends": "Template inheritance would form a cycle."})
            seen.add(parent.pk)
            parent = parent.extends
        if self.extends is not None and not self.extends.is_base_template:
            if self.granularity != self.extends.granularity:
                raise ValidationError(
                    {
                        "granularity": "An override must use the same granularity as the template it "
                        f"extends ({self.extends.get_granularity_display()})."
                    }
                )
```

- [ ] **Step 4: Implement matching** in `notices/services/template_matching.py`. Keep `__init__`, `_get_event_type`, `_scope_matches`, `_get_context_object`. Replace `_score_template` with public `score`, delete the removed methods, add module functions:

```python
__all__ = ("TemplateMatchingService", "kinds_for_event", "merge_templates", "resolve_chain")

    def score(self, template):
        """Return the template's score for this context, or None when it does not apply."""
        scopes = list(template.scopes.all())
        if not scopes:
            return template.weight
        matched = [scope.weight for scope in scopes if self._scope_matches(scope)]
        if not matched:
            return None
        return template.weight + sum(matched)


def kinds_for_event(event):
    """Independent notification kinds for an event: non-base templates that override nothing."""
    from notices.models import NotificationTemplate

    event_type = event._meta.model_name
    return (
        NotificationTemplate.objects.filter(
            Q(event_type=event_type) | Q(event_type=MessageEventTypeChoices.BOTH),
            is_base_template=False,
        )
        .filter(Q(extends__isnull=True) | Q(extends__is_base_template=True))
        .prefetch_related("scopes__content_type", "contact_roles", "children")
    )


def resolve_chain(root, matcher):
    """
    Return the inheritance chain to render for one recipient group, most specific first.

    Starting at the root kind, descend into the highest-scoring override that applies to the
    matcher's context, repeatedly; then append the root's base-template ancestors, which only
    contribute layout and fallback fields.
    """
    chain = [root]
    current = root
    while True:
        scored = [
            (score, child)
            for child in current.children.filter(is_base_template=False).prefetch_related("scopes__content_type")
            if (score := matcher.score(child)) is not None
        ]
        if not scored:
            break
        scored.sort(key=lambda pair: pair[0], reverse=True)
        current = scored[0][1]
        chain.insert(0, current)
    ancestor = root.extends
    while ancestor is not None:
        chain.append(ancestor)
        ancestor = ancestor.extends
    return chain
```

In `merge_templates`: remove the `"extends": None` key and the "Extends - first non-null wins" block; add `"granularity"` computed after the loop as `next((t.granularity for t in reversed(templates) if not t.is_base_template), templates[-1].granularity)`. Update its docstring: "templates: inheritance chain, most specific first (see resolve_chain)".

- [ ] **Step 5: Run tests** (same command as Step 2). Expected: all pass. Also run `tests/test_messaging_api.py tests/test_messaging_views.py -q` to confirm nothing else used the removed functions (`grep -rn "find_matching_templates\|get_best_template\|get_merged_config\|find_templates" notices tests` must return nothing).

- [ ] **Step 6: Lint and commit**

```bash
/opt/netbox/venv/bin/ruff check --fix notices/ tests/ && /opt/netbox/venv/bin/ruff format notices/ tests/
git add notices/services/template_matching.py notices/models/messaging.py tests/test_template_matching.py tests/test_messaging_models.py
git commit -m "refactor(templates): match kinds and overrides along extends"
```

---

### Task 2: Chain-aware rendering and body formats

**Files:**
- Modify: `notices/services/template_renderer.py`
- Test: `tests/test_template_renderer.py`

**Interfaces:**
- Consumes: `resolve_chain` output shape (list of `NotificationTemplate`, most specific first) from Task 1.
- Produces (used by Task 5):
  - `TemplateRenderer.for_chain(chain) -> TemplateRenderer`: classmethod; registers every chain member's `body_template` under its slug and resolves `{% extends "base" %}` inside template X to X's own parent.
  - `TemplateRenderer.render_body(chain, context) -> str`: renders the first chain member with a non-empty `body_template` by name (so inheritance works) WITH context.
  - `split_body(body_format, rendered) -> tuple[str, str]` module function: returns `(body_text, body_html)`.
- Removed: `TemplateRenderer.render_with_inheritance` (dead; only its test used it -- rewrite that test).

- [ ] **Step 1: Write failing tests** (replace `test_render_with_blocks`):

```python
from notices.services.template_renderer import TemplateRenderer, split_body


def _chain(*specs):
    """Build unsaved templates linked by extends: specs are (slug, body), most specific first."""
    from notices.models import NotificationTemplate

    templates = [NotificationTemplate(name=s, slug=s, body_template=b) for s, b in specs]
    for child, parent in zip(templates, templates[1:]):
        child.extends = parent
    return templates


class TestChainRendering:
    def test_child_block_overrides_parent_with_context(self):
        chain = _chain(
            ("child", '{% extends "base" %}{% block content %}hi {{ name }}{% endblock %}'),
            ("parent", "[{% block content %}default{% endblock %}]"),
        )
        renderer = TemplateRenderer.for_chain(chain)
        assert renderer.render_body(chain, {"name": "acme"}) == "[hi acme]"

    def test_three_level_base_resolves_to_each_parent(self):
        chain = _chain(
            ("leaf", '{% extends "base" %}{% block a %}LEAF{% endblock %}'),
            ("mid", '{% extends "base" %}{% block b %}MID{% endblock %}'),
            ("top", "{% block a %}a{% endblock %}-{% block b %}b{% endblock %}"),
        )
        assert TemplateRenderer.for_chain(chain).render_body(chain, {}) == "LEAF-MID"

    def test_empty_child_body_falls_back_to_parent(self):
        chain = _chain(("child", ""), ("parent", "P {{ x }}"))
        assert TemplateRenderer.for_chain(chain).render_body(chain, {"x": 1}) == "P 1"


class TestSplitBody:
    def test_markdown_keeps_source_as_text_and_renders_html(self):
        text, html = split_body("markdown", "**hi**")
        assert text == "**hi**"
        assert "<strong>hi</strong>" in html

    def test_html_strips_tags_for_text(self):
        text, html = split_body("html", "<p>hi <b>there</b></p>")
        assert html == "<p>hi <b>there</b></p>"
        assert text == "hi there"

    def test_text_has_no_html(self):
        assert split_body("text", "plain") == ("plain", "")
```

- [ ] **Step 2: Run** `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/test_template_renderer.py -q` -- expect ImportError on `split_body`, then failures.

- [ ] **Step 3: Implement** in `notices/services/template_renderer.py`:

```python
from django.utils.html import strip_tags

__all__ = ("TemplateRenderer", "TemplateRenderError", "split_body")


class ChainEnvironment(Environment):
    """Jinja environment where `{% extends "base" %}` means "my own parent template"."""

    def __init__(self, parents, **kwargs):
        super().__init__(**kwargs)
        self.parents = parents

    def join_path(self, template, parent):
        if template == "base" and parent in self.parents:
            return self.parents[parent]
        return template


def split_body(body_format, rendered):
    """Return (body_text, body_html) for a rendered body according to its format."""
    if body_format == "markdown":
        return rendered, render_markdown(rendered)
    if body_format == "html":
        return strip_tags(rendered).strip(), rendered
    return rendered, ""
```

Change `TemplateRenderer.__init__(self, templates=None, parents=None)`; when `parents` is given use `ChainEnvironment(parents, loader=..., autoescape=False)`, else plain `Environment`. Register filters in both cases. Add:

```python
    @classmethod
    def for_chain(cls, chain):
        """Renderer whose loader knows every template in an inheritance chain by slug."""
        templates = {t.slug: t.body_template or "" for t in chain}
        parents = {t.slug: t.extends.slug for t in chain if t.extends_id is not None or t.extends is not None}
        return cls(templates=templates, parents=parents)

    def render_body(self, chain, context):
        """Render the most specific non-empty body in the chain, with inheritance and context."""
        source = next((t for t in chain if t.body_template), None)
        if source is None:
            return ""
        try:
            return self.env.get_template(source.slug).render(**context)
        except (TemplateSyntaxError, UndefinedError) as e:
            raise TemplateRenderError(f"Template rendering failed: {e}")
```

Note: unsaved templates in tests have `extends` set but `extends_id` None -- that is why `for_chain` checks both. Delete `render_with_inheritance`. Check `build_context`'s first parameter `notification_template`: if it is unused in the body, leave the signature (callers pass it) -- do not widen scope.

- [ ] **Step 4: Run tests** (Step 2 command). Expected PASS.

- [ ] **Step 5: Lint and commit**

```bash
git add notices/services/template_renderer.py tests/test_template_renderer.py
git commit -m "feat(services): render template chains with context and body formats"
```

---

### Task 3: Recipient grouping helpers

**Files:**
- Modify: `notices/services/recipient_discovery.py`
- Test: `tests/test_recipient_discovery.py`

**Interfaces:**
- Produces (used by Task 5):
  - `RecipientGroup` frozen dataclass: `tenant: Tenant | None`, `impact: Impact | None`, `impacts: tuple[Impact, ...]`, `tenants: tuple[Tenant, ...]` (tenants whose contacts receive this group: per_event = all impacted tenants; per_tenant/per_impact = the one tenant or empty).
  - `group_impacts(event, granularity) -> list[RecipientGroup]`.
  - `contacts_for_tenants(tenants, roles, priorities) -> list[Contact]`: unique contacts, order of first appearance.
  - `tenant_for_impact(impact) -> Tenant | None`.
- The existing `RecipientDiscoveryService` methods must delegate to these (no parallel implementations); keep its public API (`discover_for_event`, `discover_for_tenant`) and `discover_recipients`.

- [ ] **Step 1: Write failing tests** (add to `tests/test_recipient_discovery.py`; reuse its existing fixtures for tenants/circuits/contact assignments -- read the file first and adapt fixture names):

```python
from notices.services.recipient_discovery import contacts_for_tenants, group_impacts


@pytest.mark.django_db
class TestGroupImpacts:
    def test_per_event_single_group_with_all_tenants(self, maintenance_with_two_tenants):
        event, tenant_a, tenant_b = maintenance_with_two_tenants
        [group] = group_impacts(event, "per_event")
        assert group.tenant is None and group.impact is None
        assert set(group.tenants) == {tenant_a, tenant_b}
        assert len(group.impacts) == event.impacts.count()

    def test_per_tenant_one_group_per_tenant(self, maintenance_with_two_tenants):
        event, tenant_a, tenant_b = maintenance_with_two_tenants
        groups = group_impacts(event, "per_tenant")
        assert {g.tenant for g in groups} == {tenant_a, tenant_b}
        assert all(g.tenants == (g.tenant,) for g in groups)

    def test_per_impact_one_group_per_impact(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        groups = group_impacts(event, "per_impact")
        assert {g.impact for g in groups} == set(event.impacts.all())

    def test_target_without_tenant_is_not_grouped_per_tenant(self, maintenance, site):
        from notices.models import Impact

        Impact.objects.create(event=maintenance, target=site, impact="OUTAGE")
        assert group_impacts(maintenance, "per_tenant") == []
        [group] = group_impacts(maintenance, "per_event")
        assert len(group.impacts) == 1 and group.tenants == ()
```

Add a fixture `maintenance_with_two_tenants` to `tests/conftest.py` (shared with Tasks 5, 7, 8):

```python
@pytest.fixture
def maintenance_with_two_tenants(maintenance, provider, circuit_type):
    """A maintenance impacting one circuit of each of two tenants, each with a primary NOC contact."""
    from circuits.models import Circuit
    from tenancy.models import Contact, ContactAssignment, ContactRole, Tenant

    from notices.models import Impact

    role = ContactRole.objects.create(name="NOC", slug="noc")
    tenants = []
    for idx in (1, 2):
        tenant = Tenant.objects.create(name=f"Tenant {idx}", slug=f"tenant-{idx}")
        contact = Contact.objects.create(name=f"Contact {idx}", email=f"c{idx}@example.com")
        ContactAssignment.objects.create(object=tenant, contact=contact, role=role, priority="primary")
        circuit = Circuit.objects.create(cid=f"CID-{idx}", provider=provider, type=circuit_type, tenant=tenant)
        Impact.objects.create(event=maintenance, target=circuit, impact="OUTAGE")
        tenants.append(tenant)
    return maintenance, tenants[0], tenants[1]
```

(If `ContactAssignment` rejects `object=` use `object_type=ContentType.objects.get_for_model(tenant), object_id=tenant.pk`.)

- [ ] **Step 2: Run** `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/test_recipient_discovery.py -q` -- expect ImportError.

- [ ] **Step 3: Implement** in `notices/services/recipient_discovery.py`:

```python
from dataclasses import dataclass

__all__ = (
    "RecipientDiscoveryService", "RecipientGroup", "contacts_for_tenants", "discover_recipients",
    "group_impacts", "tenant_for_impact",
)


@dataclass(frozen=True)
class RecipientGroup:
    """One outgoing notification's audience: the impacts it covers and whose contacts receive it."""

    tenant: object = None
    impact: object = None
    impacts: tuple = ()
    tenants: tuple = ()


def tenant_for_impact(impact):
    """The tenant owning an impact's target, or None when the target has no tenant."""
    return getattr(impact.target, "tenant", None) if impact.target is not None else None


def group_impacts(event, granularity):
    """Split an event's impacts into recipient groups for the given granularity."""
    from notices.choices import MessageGranularityChoices

    impacts = list(event.impacts.all())
    pairs = [(impact, tenant_for_impact(impact)) for impact in impacts]

    if granularity == MessageGranularityChoices.PER_IMPACT:
        return [
            RecipientGroup(tenant=tenant, impact=impact, impacts=(impact,), tenants=(tenant,) if tenant else ())
            for impact, tenant in pairs
        ]
    if granularity == MessageGranularityChoices.PER_TENANT:
        by_tenant = {}
        for impact, tenant in pairs:
            if tenant is not None:
                by_tenant.setdefault(tenant, []).append(impact)
        return [RecipientGroup(tenant=t, impacts=tuple(i), tenants=(t,)) for t, i in by_tenant.items()]
    tenants = tuple(dict.fromkeys(t for _, t in pairs if t is not None))
    return [RecipientGroup(impacts=tuple(impacts), tenants=tenants)]


def contacts_for_tenants(tenants, roles, priorities):
    """Unique contacts assigned to any of the tenants, filtered by role and priority (never inactive)."""
    tenants = [t for t in tenants if t is not None]
    if not tenants:
        return []
    tenant_ct = ContentType.objects.get_for_model(tenants[0])
    # NetBox names the content type field 'object_type', not 'content_type'.
    filters = Q(object_type=tenant_ct, object_id__in=[t.pk for t in tenants]) & ~Q(priority="inactive")
    if roles:
        filters &= Q(role__in=roles)
    if priorities:
        filters &= Q(priority__in=priorities)
    contacts = {}
    for assignment in ContactAssignment.objects.filter(filters).select_related("contact").order_by("pk"):
        contacts.setdefault(assignment.contact_id, assignment.contact)
    return list(contacts.values())
```

Then make `RecipientDiscoveryService._get_contacts_for_tenant(tenant)` return `contacts_for_tenants([tenant], self.roles, self.priorities)`, `_get_tenant_from_impact` call `tenant_for_impact`, and rewrite `_discover_per_event/_per_tenant/_per_impact` on top of `group_impacts` so the grouping logic exists once. Existing tests in the file must still pass unchanged (if a test asserts on the removed `impact.circuit` branch, delete that test -- `Impact` has no `circuit` attribute anymore).

- [ ] **Step 4: Run tests** (Step 2 command). Expected PASS.

- [ ] **Step 5: Lint and commit**

```bash
git add notices/services/recipient_discovery.py tests/test_recipient_discovery.py tests/conftest.py
git commit -m "refactor(services): expose recipient grouping by granularity"
```

---

### Task 4: PreparedNotification group, hashes and timeline link

**Files:**
- Modify: `notices/models/messaging.py`
- Create: `notices/migrations/0012_preparednotification_group_and_hashes.py`
- Test: `tests/test_messaging_models.py`

**Interfaces:**
- Produces (used by Tasks 5-8):
  - Fields `tenant` (FK `tenancy.Tenant`, null, SET_NULL, related_name `"+"`), `impact` (FK `notices.Impact`, null, SET_NULL, related_name `"+"`), `content_hash` (GeneratedField, CharField 32, `db_persist=True`), `rendered_hash` (CharField 32, blank, default "").
  - `PreparedNotificationQuerySet(RestrictedQuerySet)` with `modified()` and `unmodified_drafts()`; `PreparedNotification.objects = PreparedNotificationQuerySet.as_manager()`.
  - `MODIFIED_Q` module constant (Q object) and `PreparedNotification.is_modified` property.
  - `PreparedNotification.mark_rendered()` -> None: `type(self).objects.filter(pk=self.pk).update(rendered_hash=F("content_hash"))` then `refresh_from_db(fields=["rendered_hash", "content_hash"])`.
  - `to_objectchange(action)` sets `related_object` to the event.

- [ ] **Step 1: Write failing tests** in `tests/test_messaging_models.py`:

```python
@pytest.mark.django_db
class TestPreparedNotificationModified:
    def _make(self, notification_template, **kw):
        defaults = dict(template=notification_template, subject="S", body_text="B")
        defaults.update(kw)
        return PreparedNotification.objects.create(**defaults)

    def test_hand_created_is_never_modified(self, notification_template):
        n = self._make(notification_template)
        assert not n.is_modified
        assert not PreparedNotification.objects.modified().filter(pk=n.pk).exists()

    def test_edit_after_render_is_modified(self, notification_template):
        n = self._make(notification_template)
        n.mark_rendered()
        assert not n.is_modified
        n.body_text = "edited"
        n.save()
        assert n.is_modified
        assert PreparedNotification.objects.modified().filter(pk=n.pk).exists()

    def test_header_key_order_is_not_a_modification(self, notification_template):
        n = self._make(notification_template, headers={"a": "1", "b": "2"})
        n.mark_rendered()
        n.headers = {"b": "2", "a": "1"}
        n.save()
        assert not n.is_modified

    def test_objectchange_relates_to_event(self, notification_template, maintenance):
        n = self._make(notification_template, event=maintenance)
        assert n.to_objectchange("update").related_object == maintenance
```

`notification_template` fixture: if not available in this module, copy the one from `tests/test_messaging_api.py` into `tests/conftest.py` (and delete it from `test_messaging_api.py` to avoid duplication).

- [ ] **Step 2: Run** `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/test_messaging_models.py -q` -- expect AttributeError `mark_rendered`.

- [ ] **Step 3: Implement the model** in `notices/models/messaging.py`:

```python
from django.db.models import F, Q, Value
from django.db.models.functions import MD5, Cast, Coalesce, Concat

# Separator between hashed fields so moving text across a boundary still changes the hash.
_HASH_SEPARATOR = Value("\x1f")
_HASHED_TEXT_FIELDS = ("subject", "body_text", "body_html", "css", "ical_content")


def _content_hash_expression():
    parts = [Coalesce(Cast("headers", models.TextField()), Value(""))]
    for name in _HASHED_TEXT_FIELDS:
        parts += [_HASH_SEPARATOR, Coalesce(name, Value(""))]
    return MD5(Concat(*parts, output_field=models.TextField()))


# A notification is modified when it was generated (rendered_hash set) and its content has
# since diverged from what was rendered.
MODIFIED_Q = ~Q(rendered_hash="") & ~Q(rendered_hash=F("content_hash"))


class PreparedNotificationQuerySet(RestrictedQuerySet):
    def modified(self):
        return self.filter(MODIFIED_Q)
```

On `PreparedNotification` add (after `ical_content`):

```python
    # Recipient group this notification was generated for (see NotificationGenerator).
    tenant = models.ForeignKey(
        to="tenancy.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    impact = models.ForeignKey(
        to="notices.Impact", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    # Postgres recomputes content_hash on every write; rendered_hash is the value it had right
    # after generation. Comparing them in SQL detects hand edits without hashing in Python.
    content_hash = models.GeneratedField(
        expression=_content_hash_expression(),
        output_field=models.CharField(max_length=32),
        db_persist=True,
    )
    rendered_hash = models.CharField(max_length=32, blank=True, default="", editable=False)

    objects = PreparedNotificationQuerySet.as_manager()
```

and methods:

```python
    @property
    def is_modified(self):
        return bool(self.rendered_hash) and self.rendered_hash != self.content_hash

    def mark_rendered(self):
        """Record the current content as the generated baseline (copied inside Postgres)."""
        type(self).objects.filter(pk=self.pk).update(rendered_hash=F("content_hash"))
        self.refresh_from_db(fields=["rendered_hash", "content_hash"])

    def to_objectchange(self, action):
        """File changes against the linked event so they appear on its timeline."""
        objectchange = super().to_objectchange(action)
        if self.event is not None:
            objectchange.related_object = self.event
        return objectchange
```

Make `SentNotificationManager` derive from `models.Manager.from_queryset(PreparedNotificationQuerySet)`. Use `PreparedNotification.objects.filter(...)` (not `type(self).objects`) inside `mark_rendered` if `SentNotification` instances could call it -- the proxy manager filters by status; using the concrete model's manager is correct.

- [ ] **Step 4: Write the migration** by hand, `notices/migrations/0012_preparednotification_group_and_hashes.py`:

```python
import django.db.models.deletion
import django.db.models.functions
from django.db import migrations, models

import notices.models.messaging


class Migration(migrations.Migration):
    dependencies = [
        ("notices", "0011_alter_preparednotification_headers_and_more"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="preparednotification",
            name="tenant",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="preparednotification",
            name="impact",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="notices.impact",
            ),
        ),
        migrations.AddField(
            model_name="preparednotification",
            name="rendered_hash",
            field=models.CharField(blank=True, default="", editable=False, max_length=32),
        ),
        migrations.AddField(
            model_name="preparednotification",
            name="content_hash",
            field=models.GeneratedField(
                db_persist=True,
                expression=notices.models.messaging._content_hash_expression(),
                output_field=models.CharField(max_length=32),
            ),
        ),
    ]
```

Then verify the migration is complete by running, from the worktree, `PYTHONPATH=$PWD:/opt/netbox/netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py makemigrations notices --check --dry-run` (PYTHONPATH puts the worktree first). If it reports changes, adjust the hand-written migration to match (do not let it write a file into the main checkout -- `--dry-run` guarantees that). If Postgres rejects the expression as not immutable, inspect `ConcatPair.as_postgresql` and replace `Concat` with explicit `||` via `Func(..., template="(%(expressions)s)", arg_joiner=" || ")` keeping `COALESCE` per operand; the md5-of-`||` form was verified immutable on PostgreSQL 17.

- [ ] **Step 5: Check GraphQL** -- `notices/graphql/types.py` uses `fields="__all__"` for `PreparedNotification`. Run `tests/test_graphql*.py` if present, otherwise `-k graphql`; if the schema fails on the GeneratedField, exclude `content_hash` and `rendered_hash` from the type with `exclude=[...]`.

- [ ] **Step 6: Run** the Step 2 command plus `tests/test_messaging_api.py`. Expected PASS.

- [ ] **Step 7: Lint and commit**

```bash
git add notices/models/messaging.py notices/migrations/0012_preparednotification_group_and_hashes.py tests/
git commit -m "feat(models): track notification group and generated content hash"
```

---

### Task 5: NotificationGenerator service

**Files:**
- Create: `notices/services/notification_generation.py`
- Modify: `notices/services/__init__.py` (export)
- Modify: `notices/choices.py` (add `GenerationActionChoices`)
- Test: `tests/test_notification_generation.py`

**Interfaces:**
- Consumes: Task 1 (`kinds_for_event`, `resolve_chain`, `merge_templates`, `TemplateMatchingService`, `root_kind`), Task 2 (`TemplateRenderer.for_chain`, `render_body`, `split_body`, `build_context`), Task 3 (`group_impacts`, `contacts_for_tenants`, `RecipientGroup`), Task 4 (fields, `mark_rendered`, `is_modified`), existing `generate_ical(template, event, tenant=None, impacts=None, message_sequence=1)`.
- Produces (used by Tasks 7, 8, 9):
  - `GenerationActionChoices` in `notices/choices.py`: `CREATE="create"`, `UPDATE="update"`, `KEEP="keep"`, `DELETE="delete"`, `SKIP="skip"`, `ERROR="error"` with colors green/blue/gray/red/yellow/red.
  - `PlannedNotification` dataclass: `action`, `root_template`, `template`, `tenant`, `impact`, `contacts` (list), `content` (dict with keys `subject, body_text, body_html, headers, css, ical_content`), `existing` (PreparedNotification|None), `error` (str|None), `notification` (PreparedNotification|None, set by apply).
  - `NotificationGenerator(event, templates=None)`; `.plan() -> list[PlannedNotification]`; `.apply(plan) -> GenerationResult`; `.reset(notification) -> PreparedNotification`.
  - `GenerationResult` dataclass: `items: list[PlannedNotification]`, `counts: dict[str, int]` (per action), `summary() -> str` e.g. `"2 created, 1 updated, 1 kept, 1 skipped"` (omit zero counts; "Nothing to generate" when empty).
  - `NotificationGenerator.applicable_kinds() -> QuerySet` (= `kinds_for_event(event)`), used by the UI checkbox list.
  - Raises `ValueError` from `reset()` when the notification is not a draft or has no event.

- [ ] **Step 1: Write failing tests** `tests/test_notification_generation.py`:

```python
"""Tests for NotificationGenerator."""

import pytest
from django.contrib.contenttypes.models import ContentType

from notices.models import NotificationTemplate, PreparedNotification, TemplateScope
from notices.services.notification_generation import NotificationGenerator


def _kind(slug, **kw):
    defaults = dict(
        name=slug, slug=slug, event_type="maintenance", granularity="per_tenant",
        subject_template="{{ maintenance.name }} for {{ tenant.name if tenant else 'all' }}",
        body_template="Body {{ tenant_impacts|length }}", body_format="text",
    )
    defaults.update(kw)
    return NotificationTemplate.objects.create(**defaults)


def _actions(plan):
    return sorted(item.action for item in plan)


@pytest.mark.django_db
class TestPlan:
    def test_one_draft_per_tenant(self, maintenance_with_two_tenants):
        event, tenant_a, tenant_b = maintenance_with_two_tenants
        _kind("customer")
        plan = NotificationGenerator(event).plan()
        assert _actions(plan) == ["create", "create"]
        assert {item.tenant for item in plan} == {tenant_a, tenant_b}
        assert plan[0].content["subject"].startswith("MAINT-001 for Tenant")
        assert PreparedNotification.objects.count() == 0  # plan has no side effects

    def test_each_kind_generates_independently(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("customer")
        _kind("noc", granularity="per_event")
        assert len(NotificationGenerator(event).plan()) == 3

    def test_tenant_override_replaces_root_for_that_tenant(self, maintenance_with_two_tenants):
        event, tenant_a, _ = maintenance_with_two_tenants
        root = _kind("customer")
        acme = _kind("customer-a", extends=root, subject_template="Special")
        TemplateScope.objects.create(
            template=acme, content_type=ContentType.objects.get_for_model(tenant_a), object_id=tenant_a.pk
        )
        plan = {item.tenant: item for item in NotificationGenerator(event).plan()}
        assert plan[tenant_a].template == acme and plan[tenant_a].content["subject"] == "Special"
        assert plan[tenant_a].root_template == root

    def test_group_without_contacts_is_skipped(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("customer", contact_priorities=["tertiary"])
        assert _actions(NotificationGenerator(event).plan()) == ["skip", "skip"]

    def test_render_error_only_marks_its_own_kind(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("good", granularity="per_event")
        _kind("bad", granularity="per_event", body_template="{% if %}")
        plan = {item.root_template.slug: item for item in NotificationGenerator(event).plan()}
        assert plan["good"].action == "create"
        assert plan["bad"].action == "error" and plan["bad"].error

    def test_long_subject_is_truncated(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("long", granularity="per_event", subject_template="x" * 400)
        [item] = NotificationGenerator(event).plan()
        assert len(item.content["subject"]) == 255


@pytest.mark.django_db
class TestRegeneration:
    def _generate(self, event, **kw):
        gen = NotificationGenerator(event, **kw)
        return gen.apply(gen.plan())

    def test_untouched_draft_is_updated_in_place(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        kind = _kind("noc", granularity="per_event")
        self._generate(event)
        kind.subject_template = "New subject"
        kind.save()
        result = self._generate(event)
        assert result.counts == {"update": 1}
        assert PreparedNotification.objects.get().subject == "New subject"

    def test_modified_draft_is_kept(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("noc", granularity="per_event")
        self._generate(event)
        n = PreparedNotification.objects.get()
        n.body_text = "hand edit"
        n.save()
        assert self._generate(event).counts == {"keep": 1}
        assert PreparedNotification.objects.get().body_text == "hand edit"

    def test_sent_notification_kept_and_new_draft_created(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("noc", granularity="per_event", include_ical=True, ical_template="SEQ:{{ message_sequence }}")
        self._generate(event)
        PreparedNotification.objects.update(status="sent")
        result = self._generate(event)
        assert result.counts == {"create": 1}
        new = PreparedNotification.objects.get(status="draft")
        assert new.ical_content == "SEQ:2"

    def test_stale_untouched_draft_is_deleted(self, maintenance_with_two_tenants):
        event, tenant_a, _ = maintenance_with_two_tenants
        _kind("customer")
        self._generate(event)
        event.impacts.filter(target_object_id__in=tenant_a.circuits.values("pk")).delete()
        assert self._generate(event).counts == {"update": 1, "delete": 1}

    def test_unselected_kind_drafts_survive(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        a = _kind("a", granularity="per_event")
        _kind("b", granularity="per_event")
        self._generate(event)
        self._generate(event, templates=[a])
        assert PreparedNotification.objects.count() == 2

    def test_apply_sets_group_and_baseline(self, maintenance_with_two_tenants):
        event, tenant_a, _ = maintenance_with_two_tenants
        _kind("customer")
        self._generate(event)
        n = PreparedNotification.objects.get(tenant=tenant_a)
        assert n.event == event and not n.is_modified and n.rendered_hash
        assert list(n.contacts.values_list("email", flat=True)) == ["c1@example.com"]


@pytest.mark.django_db
class TestReset:
    def test_reset_discards_edits(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("noc", granularity="per_event")
        gen = NotificationGenerator(event)
        gen.apply(gen.plan())
        n = PreparedNotification.objects.get()
        original = n.body_text
        n.body_text = "edited"
        n.save()
        n = NotificationGenerator(event).reset(n)
        assert n.body_text == original and not n.is_modified

    def test_reset_rejects_non_draft(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("noc", granularity="per_event")
        gen = NotificationGenerator(event)
        gen.apply(gen.plan())
        n = PreparedNotification.objects.get()
        n.status = "ready"
        with pytest.raises(ValueError):
            NotificationGenerator(event).reset(n)
```

(The `tenant_a.circuits` reverse accessor: if it does not exist, filter circuits with `Circuit.objects.filter(tenant=tenant_a)`.)

- [ ] **Step 2: Run** `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/test_notification_generation.py -q` -- expect ImportError.

- [ ] **Step 3: Add choices** to `notices/choices.py`:

```python
class GenerationActionChoices(ChoiceSet):
    """What a generation run does with one recipient group."""

    CREATE = "create"
    UPDATE = "update"
    KEEP = "keep"
    DELETE = "delete"
    SKIP = "skip"
    ERROR = "error"

    CHOICES = [
        (CREATE, "Create", "green"),
        (UPDATE, "Update", "blue"),
        (KEEP, "Keep", "gray"),
        (DELETE, "Delete", "red"),
        (SKIP, "Skip", "yellow"),
        (ERROR, "Error", "red"),
    ]
```

- [ ] **Step 4: Implement** `notices/services/notification_generation.py` (complete module; deviate only where a failing test proves an assumption about NetBox wrong, and say so in your report):

```python
"""
Turn a Maintenance or Outage into draft PreparedNotifications.

plan() is side-effect free so the same code drives the UI preview, the API dry run and auto
mode; apply() writes a plan in one transaction.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from types import SimpleNamespace

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from notices.choices import GenerationActionChoices as Action
from notices.choices import PreparedNotificationStatusChoices as Status
from notices.services.ical_generation import generate_ical
from notices.services.recipient_discovery import RecipientGroup, contacts_for_tenants, group_impacts
from notices.services.template_matching import (
    TemplateMatchingService,
    kinds_for_event,
    merge_templates,
    resolve_chain,
)
from notices.services.template_renderer import TemplateRenderer, TemplateRenderError, split_body

__all__ = ("GenerationResult", "NotificationGenerator", "PlannedNotification")

SUBJECT_MAX_LENGTH = 255

_PAST_TENSE = {
    Action.CREATE: "created",
    Action.UPDATE: "updated",
    Action.KEEP: "kept",
    Action.DELETE: "deleted",
    Action.SKIP: "skipped",
    Action.ERROR: "failed",
}


@dataclass
class PlannedNotification:
    """What one generation run intends to do for one recipient group."""

    action: str
    root_template: object
    template: object = None
    tenant: object = None
    impact: object = None
    contacts: list = field(default_factory=list)
    content: dict = field(default_factory=dict)
    existing: object = None
    error: str = None
    notification: object = None


@dataclass
class GenerationResult:
    items: list
    counts: dict

    @classmethod
    def from_plan(cls, plan):
        return cls(items=plan, counts=dict(Counter(item.action for item in plan)))

    def summary(self):
        parts = [f"{count} {_PAST_TENSE[action]}" for action, count in self.counts.items() if count]
        return ", ".join(parts) or "Nothing to generate"


def _group_key(root_pk, tenant, impact):
    return (root_pk, getattr(tenant, "pk", None), getattr(impact, "pk", None))


def _notifications_for_event(event):
    from notices.models import PreparedNotification

    return PreparedNotification.objects.filter(
        event_content_type=ContentType.objects.get_for_model(event), event_id=event.pk
    ).select_related("template__extends", "tenant", "impact")


def _delete_item(notification):
    return PlannedNotification(
        Action.DELETE,
        notification.template.root_kind,
        notification.template,
        notification.tenant,
        notification.impact,
        existing=notification,
    )


class NotificationGenerator:
    def __init__(self, event, templates=None):
        self.event = event
        self.templates = list(templates) if templates is not None else None

    def applicable_kinds(self):
        return kinds_for_event(self.event)

    def plan(self):
        kinds = self.templates if self.templates is not None else list(self.applicable_kinds())
        existing = self._existing_by_group({kind.pk for kind in kinds})
        items = []
        for root in kinds:
            for group in group_impacts(self.event, root.granularity):
                matcher = TemplateMatchingService(event=self.event, tenant=group.tenant)
                if matcher.score(root) is None:
                    continue  # this kind does not apply to this group; leftovers handled below
                siblings = existing.pop(_group_key(root.pk, group.tenant, group.impact), [])
                items += self._plan_group(root, group, matcher, siblings)
        # Groups that no longer exist (or no longer match): drop their untouched drafts.
        for siblings in existing.values():
            items += [_delete_item(n) for n in siblings if n.status == Status.DRAFT and not n.is_modified]
        return items

    @transaction.atomic
    def apply(self, plan):
        from notices.models import PreparedNotification

        for item in plan:
            if item.action == Action.DELETE:
                item.existing.delete()
                continue
            if item.action == Action.CREATE:
                item.notification = PreparedNotification(
                    template=item.template,
                    event=self.event,
                    tenant=item.tenant,
                    impact=item.impact,
                    status=Status.DRAFT,
                    **item.content,
                )
            elif item.action == Action.UPDATE:
                item.notification = item.existing
                item.notification.snapshot()
                item.notification.template = item.template
                for name, value in item.content.items():
                    setattr(item.notification, name, value)
            else:
                continue
            # No full_clean(): it would try to validate the database-generated content_hash.
            item.notification.save()
            item.notification.contacts.set(item.contacts)
            item.notification.mark_rendered()
        return GenerationResult.from_plan(plan)

    def reset(self, notification):
        """Re-render one draft from its template family, event and group, discarding edits."""
        if notification.status != Status.DRAFT or notification.event is None:
            raise ValueError("Only drafts linked to an event can be reset.")
        root = notification.template.root_kind
        group = self._group_for(notification, root.granularity)
        matcher = TemplateMatchingService(event=self.event, tenant=group.tenant)
        siblings = [
            n
            for n in _notifications_for_event(self.event)
            if n.template.root_kind.pk == root.pk
            and (n.tenant_id, n.impact_id) == (notification.tenant_id, notification.impact_id)
        ]
        item = self._render_item(
            root, group, matcher, sent_count=self._sent_count(siblings), require_contacts=False
        )
        if item.action == Action.ERROR:
            raise TemplateRenderError(item.error)
        item.action, item.existing = Action.UPDATE, notification
        self.apply([item])
        return notification

    # -- internals --------------------------------------------------------------------------

    def _existing_by_group(self, root_pks):
        by_group = defaultdict(list)
        for n in _notifications_for_event(self.event):
            root = n.template.root_kind
            if root.pk in root_pks:
                by_group[_group_key(root.pk, n.tenant, n.impact)].append(n)
        return by_group

    @staticmethod
    def _sent_count(siblings):
        return sum(1 for n in siblings if n.status != Status.DRAFT)

    def _plan_group(self, root, group, matcher, siblings):
        drafts = [n for n in siblings if n.status == Status.DRAFT]
        untouched = [n for n in drafts if not n.is_modified]
        item = self._render_item(root, group, matcher, sent_count=self._sent_count(siblings))
        if item.action == Action.SKIP:
            # Nobody to notify any more: untouched drafts for this group are stale.
            return [item] + [_delete_item(n) for n in untouched]
        if item.action == Action.ERROR:
            return [item]
        modified = [n for n in drafts if n.is_modified]
        if modified:
            item.action, item.existing = Action.KEEP, modified[0]
            return [item]
        if untouched:
            item.action, item.existing = Action.UPDATE, untouched[0]
            return [item] + [_delete_item(n) for n in untouched[1:]]
        return [item]

    def _render_item(self, root, group, matcher, sent_count, require_contacts=True):
        chain = resolve_chain(root, matcher)
        config = merge_templates(chain)
        item = PlannedNotification(Action.CREATE, root, chain[0], group.tenant, group.impact)
        item.contacts = contacts_for_tenants(group.tenants, config["contact_roles"], config["contact_priorities"])
        if require_contacts and not item.contacts:
            item.action = Action.SKIP
            return item
        impacts = list(group.impacts)
        try:
            context = TemplateRenderer.build_context(chain[0], event=self.event, tenant=group.tenant, impacts=impacts)
            renderer = TemplateRenderer.for_chain(chain)
            body_text, body_html = split_body(config["body_format"], renderer.render_body(chain, context))
            ical_source = SimpleNamespace(include_ical=config["include_ical"], ical_template=config["ical_template"])
            item.content = {
                "subject": renderer.render(config["subject_template"], context)[:SUBJECT_MAX_LENGTH],
                "body_text": body_text,
                "body_html": body_html,
                "headers": {k: renderer.render(v, context) for k, v in config["headers_template"].items()},
                "css": renderer.render(config["css_template"], context) if config["css_template"] else "",
                "ical_content": generate_ical(
                    ical_source, self.event, tenant=group.tenant, impacts=impacts, message_sequence=sent_count + 1
                )
                or "",
            }
        except TemplateRenderError as e:
            item.action, item.error = Action.ERROR, str(e)
        return item

    def _group_for(self, notification, granularity):
        for group in group_impacts(self.event, granularity):
            if (getattr(group.tenant, "pk", None), getattr(group.impact, "pk", None)) == (
                notification.tenant_id,
                notification.impact_id,
            ):
                return group
        tenant = notification.tenant
        return RecipientGroup(tenant=tenant, impact=notification.impact, tenants=(tenant,) if tenant else ())
```

Notes:
- Only `TemplateRenderError` is caught on purpose; any other exception is a bug and must surface in tests.
- `reset()` checks `notification.event` before anything else so callers may pass `NotificationGenerator(notification.event)` even when the event is None.
- Jinja `UndefinedError` is only raised for undefined attribute access on undefined objects; `TemplateRenderer.render` already converts it to `TemplateRenderError`.

- [ ] **Step 5: Export** -- add `from .notification_generation import *` to `notices/services/__init__.py`.

- [ ] **Step 6: Run** the Step 2 command, then the whole messaging/matching subset: `tests/test_notification_generation.py tests/test_template_matching.py tests/test_template_renderer.py tests/test_recipient_discovery.py tests/test_messaging_models.py`. Expected PASS.

- [ ] **Step 7: Lint and commit**

```bash
git add notices/services/ notices/choices.py tests/test_notification_generation.py
git commit -m "feat(services): add NotificationGenerator for event notifications"
```

---

### Task 6: Outgoing notifications on the event timeline

**Files:**
- Modify: `notices/timeline_utils.py`
- Test: `tests/test_timeline_utils.py`

**Interfaces:**
- Consumes: Task 4 `PreparedNotification.to_objectchange` (related_object = event).
- Produces: category `"outgoing"` from `categorize_change("preparednotification", ...)`; icon `email-arrow-right`, color `purple`.

- [ ] **Step 1: Write failing tests** (match the existing style in `tests/test_timeline_utils.py`):

```python
from notices.timeline_utils import _build_title, categorize_change, get_category_color, get_category_icon


class TestOutgoingCategory:
    def test_prepared_notification_is_outgoing(self):
        assert categorize_change("preparednotification", "create", None, {"subject": "s"}) == "outgoing"

    def test_icon_and_color(self):
        assert get_category_icon("outgoing") == "email-arrow-right"
        assert get_category_color("outgoing") == "purple"

    @pytest.mark.parametrize(
        "action,pre,post,expected",
        [
            ("create", None, {"subject": "S", "status": "draft"}, "Notification drafted: S"),
            ("update", {"subject": "S", "status": "draft"}, {"subject": "S", "status": "ready"}, "Notification approved: S"),
            ("update", {"subject": "S", "status": "ready"}, {"subject": "S", "status": "sent"}, "Notification sent: S"),
            ("update", {"subject": "S", "status": "sent"}, {"subject": "S", "status": "failed"}, "Notification failed: S"),
            ("update", {"subject": "S", "status": "draft"}, {"subject": "T", "status": "draft"}, "Notification edited: T"),
            ("delete", {"subject": "S"}, None, "Notification discarded: S"),
        ],
    )
    def test_titles(self, action, pre, post, expected):
        assert _build_title("outgoing", action, "preparednotification", "repr", pre or {}, post or {}) == expected
```

Read `_build_title`'s real signature first and adapt the call; read how `get_category_icon/color` take `status_value`.

- [ ] **Step 2: Run** `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/test_timeline_utils.py -q` -- expect failures.

- [ ] **Step 3: Implement**: in `categorize_change` add `if changed_object_model == "preparednotification": return "outgoing"` next to the `eventnotification` branch; add `"outgoing": "email-arrow-right"` / `"outgoing": "purple"` to the icon/color maps; in `_build_title` add:

```python
    elif category == "outgoing":
        subject = (postchange or prechange).get("subject", "Unknown")
        if action == "create":
            return f"Notification drafted: {subject}"
        if action == "delete":
            return f"Notification discarded: {subject}"
        old_status, new_status = prechange.get("status"), postchange.get("status")
        if new_status and new_status != old_status:
            verb = "approved" if new_status == "ready" else new_status
            return f"Notification {verb}: {subject}"
        return f"Notification edited: {subject}"
```

The create title in the spec also mentions the tenant; ObjectChange data only has `tenant` as a pk, so keep the subject-only title (the subject template normally names the customer) -- note this in the commit body.

- [ ] **Step 4: Run tests** (Step 2). Expected PASS.

- [ ] **Step 5: Lint and commit**

```bash
git add notices/timeline_utils.py tests/test_timeline_utils.py
git commit -m "feat(timeline): show outgoing notifications on the event timeline"
```

---

### Task 7: UI -- generate page, event card, approve and reset

**Files:**
- Modify: `notices/views.py`
- Create: `notices/templates/notices/generate_notifications.html`
- Create: `notices/templates/notices/inc/outgoing_notifications_card.html`
- Modify: `notices/templates/notices/maintenance.html`, `notices/templates/notices/outage.html`, `notices/templates/notices/preparednotification.html`
- Modify: `notices/filtersets.py`, `notices/tables.py`, `notices/forms.py` (filter form)
- Test: `tests/test_notification_generation_views.py`

**Interfaces:**
- Consumes: Task 5 `NotificationGenerator`, `GenerationResult.summary()`, `PlannedNotification`; Task 4 `is_modified`, `modified()`.
- Produces: URL names `plugins:notices:maintenance_generate_notifications`, `plugins:notices:outage_generate_notifications`, `plugins:notices:preparednotification_approve`, `plugins:notices:preparednotification_reset`; filterset params `event_type` (`maintenance`/`outage`), `event_id`, `tenant_id`, `modified`.

- [ ] **Step 1: Write failing tests** `tests/test_notification_generation_views.py` (plugin logic only: permission gate, preview writes nothing, POST applies with selection, approve uses state machine, reset clears modification, filterset `modified`):

```python
"""Tests for the notification generation, approve and reset views."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from notices.filtersets import PreparedNotificationFilterSet
from notices.models import NotificationTemplate, PreparedNotification
from notices.services.notification_generation import NotificationGenerator

User = get_user_model()


@pytest.fixture
def kind():
    return NotificationTemplate.objects.create(
        name="NOC", slug="noc", event_type="maintenance", granularity="per_event",
        subject_template="S {{ maintenance.name }}", body_template="B", body_format="text",
    )


@pytest.fixture
def admin_client(client):
    user = User.objects.create_superuser(username="admin2", password="x", email="a@example.com")
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestGenerateView:
    def test_requires_notification_permissions(self, client, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        user = User.objects.create_user(username="viewer", password="x")
        client.force_login(user)
        url = reverse("plugins:notices:maintenance_generate_notifications", args=[event.pk])
        assert client.post(url).status_code == 403

    def test_preview_writes_nothing(self, admin_client, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        url = reverse("plugins:notices:maintenance_generate_notifications", args=[event.pk])
        response = admin_client.get(url, {"templates": [kind.pk]})
        assert [i.action for i in response.context["plan"]] == ["create"]
        assert PreparedNotification.objects.count() == 0

    def test_post_applies_selected_kinds(self, admin_client, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        NotificationTemplate.objects.create(
            name="Other", slug="other", event_type="maintenance", granularity="per_event",
            subject_template="O", body_template="B",
        )
        url = reverse("plugins:notices:maintenance_generate_notifications", args=[event.pk])
        admin_client.post(url, {"templates": [kind.pk]})
        assert list(PreparedNotification.objects.values_list("template__slug", flat=True)) == ["noc"]


@pytest.mark.django_db
class TestApproveAndReset:
    def _generated(self, event):
        gen = NotificationGenerator(event)
        gen.apply(gen.plan())
        return PreparedNotification.objects.get()

    def test_approve_goes_through_state_machine(self, admin_client, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        n = self._generated(event)
        admin_client.post(reverse("plugins:notices:preparednotification_approve", args=[n.pk]))
        n.refresh_from_db()
        assert n.status == "ready" and n.approved_by is not None and n.recipients

    def test_reset_restores_template_content(self, admin_client, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        n = self._generated(event)
        n.body_text = "edited"
        n.save()
        admin_client.post(reverse("plugins:notices:preparednotification_reset", args=[n.pk]))
        n.refresh_from_db()
        assert n.body_text == "B" and not n.is_modified


@pytest.mark.django_db
class TestFilterSet:
    def test_modified_filter(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        gen = NotificationGenerator(event)
        gen.apply(gen.plan())
        n = PreparedNotification.objects.get()
        qs = PreparedNotification.objects.all()
        assert PreparedNotificationFilterSet({"modified": True}, qs).qs.count() == 0
        n.subject = "edited"
        n.save()
        assert list(PreparedNotificationFilterSet({"modified": True}, qs).qs) == [n]
        assert list(PreparedNotificationFilterSet({"event_type": "maintenance", "event_id": event.pk}, qs).qs) == [n]
```

- [ ] **Step 2: Run** `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/test_notification_generation_views.py -q` -- expect NoReverseMatch.

- [ ] **Step 3: Implement views** in `notices/views.py` (follow `MaintenanceAcknowledgeView` style; use `url_has_allowed_host_and_scheme` for return URLs in new views):

```python
from django.utils.http import url_has_allowed_host_and_scheme

from .services.notification_generation import NotificationGenerator
from .validators import PreparedNotificationStateMachine

GENERATE_PERMISSIONS = (
    "notices.add_preparednotification",
    "notices.change_preparednotification",
    "notices.delete_preparednotification",
)


def _safe_return_url(request, fallback):
    url = request.POST.get("return_url") or request.GET.get("return_url")
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}):
        return url
    return fallback


class BaseGenerateNotificationsView(PermissionRequiredMixin, View):
    """Preview (GET) and generate (POST) outgoing notifications for one event."""

    permission_required = GENERATE_PERMISSIONS
    model = None

    def _generator(self, request, pk):
        event = get_object_or_404(self.model.objects.restrict(request.user, "view"), pk=pk)
        kinds = NotificationGenerator(event).applicable_kinds()
        selected_ids = request.POST.getlist("templates") if request.method == "POST" else request.GET.getlist("templates")
        selected = [k for k in kinds if str(k.pk) in selected_ids] if selected_ids else list(kinds)
        return event, kinds, selected, NotificationGenerator(event, templates=selected)

    def get(self, request, pk):
        event, kinds, selected, generator = self._generator(request, pk)
        return render(
            request,
            "notices/generate_notifications.html",
            {"object": event, "kinds": kinds, "selected": selected, "plan": generator.plan()},
        )

    def post(self, request, pk):
        event, _, _, generator = self._generator(request, pk)
        result = generator.apply(generator.plan())
        messages.success(request, f"Notifications: {result.summary()}.")
        return redirect(event.get_absolute_url())


@register_model_view(models.Maintenance, "generate_notifications", path="generate-notifications")
class MaintenanceGenerateNotificationsView(BaseGenerateNotificationsView):
    model = models.Maintenance


@register_model_view(models.Outage, "generate_notifications", path="generate-notifications")
class OutageGenerateNotificationsView(BaseGenerateNotificationsView):
    model = models.Outage


@register_model_view(PreparedNotification, "approve")
class PreparedNotificationApproveView(PermissionRequiredMixin, View):
    permission_required = "notices.change_preparednotification"

    def post(self, request, pk):
        notification = get_object_or_404(PreparedNotification.objects.restrict(request.user, "change"), pk=pk)
        try:
            PreparedNotificationStateMachine(notification, user=request.user).transition_to(
                PreparedNotificationStatusChoices.READY
            )
            messages.success(request, "Notification approved.")
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))
        return redirect(_safe_return_url(request, notification.get_absolute_url()))


@register_model_view(PreparedNotification, "reset")
class PreparedNotificationResetView(PermissionRequiredMixin, View):
    permission_required = "notices.change_preparednotification"

    def post(self, request, pk):
        notification = get_object_or_404(PreparedNotification.objects.restrict(request.user, "change"), pk=pk)
        try:
            NotificationGenerator(notification.event).reset(notification)
            messages.success(request, "Notification content reset to its template.")
        except (ValueError, TemplateRenderError) as e:
            messages.error(request, str(e))
        return redirect(_safe_return_url(request, notification.get_absolute_url()))
```

Check NetBox's `register_model_view` signature for the `path` kwarg (it is `register_model_view(model, name="", path=None, detail=True, kwargs=None)`). `ValidationError` from `django.core.exceptions`; `TemplateRenderError` from `.services.template_renderer`. `PreparedNotificationStatusChoices` may already be imported in views -- reuse.

Also add `"outgoing_notifications"` to `MaintenanceView.get_extra_context` and the Outage detail view via one helper:

```python
def _outgoing_notifications(instance):
    return PreparedNotification.objects.filter(
        event_content_type=ContentType.objects.get_for_model(instance), event_id=instance.pk
    ).select_related("template", "tenant")
```

- [ ] **Step 4: Templates.**

`notices/templates/notices/generate_notifications.html`:

```django
{% extends 'generic/_base.html' %}
{% load helpers %}

{% block title %}Generate notifications: {{ object }}{% endblock %}

{% block content %}
<form method="get" class="card mb-3">
  <h5 class="card-header">Notification templates</h5>
  <div class="card-body">
    {% for kind in kinds %}
      <div class="form-check">
        <input class="form-check-input" type="checkbox" name="templates" value="{{ kind.pk }}" id="kind-{{ kind.pk }}"
               {% if kind in selected %}checked{% endif %}>
        <label class="form-check-label" for="kind-{{ kind.pk }}">{{ kind }} <span class="text-muted">({{ kind.get_granularity_display }})</span></label>
      </div>
    {% empty %}
      <div class="text-muted">No notification templates apply to this event.</div>
    {% endfor %}
  </div>
  <div class="card-footer"><button type="submit" class="btn btn-outline-primary">Preview</button></div>
</form>

<div class="card">
  <h5 class="card-header">Preview</h5>
  <table class="table table-hover">
    <thead><tr><th>Template</th><th>Group</th><th>Recipients</th><th>Action</th><th>Subject</th></tr></thead>
    <tbody>
      {% for item in plan %}
        <tr>
          <td>{{ item.template|default:item.root_template|linkify }}</td>
          <td>{% if item.impact %}{{ item.impact.target }}{% elif item.tenant %}{{ item.tenant|linkify }}{% else %}All{% endif %}</td>
          <td>{% for c in item.contacts %}{{ c.name }}{% if not forloop.last %}, {% endif %}{% empty %}<span class="text-muted">none</span>{% endfor %}</td>
          <td>{% badge item.action %}</td>
          <td>{% if item.error %}<span class="text-danger">{{ item.error }}</span>{% else %}{{ item.content.subject|default:item.existing.subject }}{% endif %}</td>
        </tr>
      {% empty %}
        <tr><td colspan="5" class="text-muted">Nothing to generate.</td></tr>
      {% endfor %}
    </tbody>
  </table>
  <form method="post" class="card-footer">
    {% csrf_token %}
    {% for kind in selected %}<input type="hidden" name="templates" value="{{ kind.pk }}">{% endfor %}
    <button type="submit" class="btn btn-primary" {% if not plan %}disabled{% endif %}>Generate</button>
    <a href="{{ object.get_absolute_url }}" class="btn btn-outline-secondary">Cancel</a>
  </form>
</div>
{% endblock %}
```

(Check `generic/_base.html` exists in NetBox 4.5 templates; otherwise use `base/layout.html` as the other plugin pages do -- grep `notices/templates` for the base used by `maintenance_cancel.html` and copy it.)

`notices/templates/notices/inc/outgoing_notifications_card.html`:

```django
{% load helpers %}
<div class="card">
  <h5 class="card-header">Outgoing Notifications</h5>
  {% if outgoing_notifications %}
    <table class="table table-hover">
      <thead><tr><th>Subject</th><th>Group</th><th>Status</th></tr></thead>
      <tbody>
        {% for n in outgoing_notifications %}
          <tr>
            <td>{{ n|linkify:"subject" }}{% if n.is_modified %} <span class="badge text-bg-warning">modified</span>{% endif %}</td>
            <td>{{ n.tenant|linkify|placeholder }}</td>
            <td>{% badge n.get_status_display bg_color=n.get_status_color %}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% else %}
    <div class="card-body text-muted">No outgoing notifications yet.</div>
  {% endif %}
  <div class="card-footer text-end">
    <a href="{% url 'plugins:notices:preparednotification_list' %}?event_type={{ object|meta:'model_name' }}&event_id={{ object.pk }}" class="btn btn-sm btn-outline-primary">All notifications</a>
  </div>
</div>
```

(`linkify:"subject"` -- check the NetBox `linkify` filter signature; if it takes an attr name, fine, else use `<a href="{{ n.get_absolute_url }}">{{ n.subject }}</a>`. `get_status_color` exists only if the ChoiceSet has colors; otherwise use plain `badge`.)

In `maintenance.html` and `outage.html`: include the card in the right-hand column next to the received-notifications card: `{% include 'notices/inc/outgoing_notifications_card.html' %}`; in the Operations dropdown add, before the final divider:

```django
                {% if perms.notices.add_preparednotification %}
                <li>
                    <a class="dropdown-item" href="{% url 'plugins:notices:maintenance_generate_notifications' pk=object.pk %}">
                        <i class="mdi mdi-email-arrow-right"></i> Generate Notifications
                    </a>
                </li>
                {% endif %}
```

(outage: `outage_generate_notifications`; check outage.html's dropdown structure and permission guard.)

In `preparednotification.html` add an `extra_controls` block:

```django
{% block extra_controls %}
  {% if perms.notices.change_preparednotification and object.status == 'draft' %}
    {% if object.event and object.is_modified %}
      <form method="post" action="{% url 'plugins:notices:preparednotification_reset' pk=object.pk %}" class="d-inline">
        {% csrf_token %}
        <button type="submit" class="btn btn-warning"><i class="mdi mdi-restore"></i> Reset to template</button>
      </form>
    {% endif %}
    <form method="post" action="{% url 'plugins:notices:preparednotification_approve' pk=object.pk %}" class="d-inline">
      {% csrf_token %}
      <button type="submit" class="btn btn-success"><i class="mdi mdi-check"></i> Approve</button>
    </form>
  {% endif %}
{% endblock %}
```

and in "Notification Details" add rows for Group (`object.impact.target` / `object.tenant|linkify` / "All") and a Modified badge when `object.is_modified`. Note `SentNotificationView` reuses this template; it is never draft, so the controls stay hidden.

- [ ] **Step 5: Filterset, table, filter form.**

`notices/filtersets.py` `PreparedNotificationFilterSet`:

```python
    event_type = django_filters.ChoiceFilter(
        choices=(("maintenance", "Maintenance"), ("outage", "Outage")),
        field_name="event_content_type__model",
    )
    event_id = django_filters.NumberFilter()
    tenant_id = django_filters.ModelMultipleChoiceFilter(queryset=Tenant.objects.all(), field_name="tenant")
    modified = django_filters.BooleanFilter(method="filter_modified")

    def filter_modified(self, queryset, name, value):
        return queryset.filter(MODIFIED_Q) if value else queryset.exclude(MODIFIED_Q)
```

Add the new names to `Meta.fields`. Import `MODIFIED_Q` from `notices.models.messaging`.

`notices/tables.py` `PreparedNotificationTable`: add `event = tables.Column(linkify=True, orderable=False)`, `tenant = tables.Column(linkify=True)`, `is_modified = columns.BooleanColumn(verbose_name="Modified", orderable=False)`; add `"event", "tenant", "is_modified"` to `fields` and `"tenant"` to `default_columns`.

`notices/forms.py` `PreparedNotificationFilterForm`: add `tenant_id = DynamicModelMultipleChoiceField(queryset=Tenant.objects.all(), required=False, label="Tenant")` and `modified = forms.NullBooleanField(required=False, widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES))` and put them in its fieldsets (read the class first for the pattern used there).

- [ ] **Step 6: Run** Step 2 command, then the full suite once: `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/ -q`. Also render-check by hand in a Django shell that `maintenance.html` still renders (the existing view tests in `tests/test_views.py` cover the detail page). Expected PASS.

- [ ] **Step 7: Lint and commit**

```bash
git add notices/ tests/test_notification_generation_views.py
git commit -m "feat(views): generate, approve and reset notifications from the UI"
```

---

### Task 8: REST API actions

**Files:**
- Modify: `notices/api/views/events.py`, `notices/api/views/messaging.py`
- Modify: `notices/api/serializers/messaging.py`
- Test: `tests/test_notification_generation_api.py`

**Interfaces:**
- Consumes: Task 5 generator; Task 4 fields.
- Produces: `POST /api/plugins/notices/maintenance/{id}/generate-notifications/`, same under `outage/`; body `{"templates": [ids], "dry_run": bool}`; response `{"summary": str, "counts": {...}, "items": [{"action", "template", "root_template", "tenant", "impact", "contacts", "subject", "error", "notification"}]}` where ids are integers or null. `POST /api/plugins/notices/prepared-notifications/{id}/reset/` returns the serialized notification. Serializer gains read-only `tenant`, `impact` (ids, `PrimaryKeyRelatedField(read_only=True)`) and `modified` (`BooleanField(source="is_modified", read_only=True)`).

- [ ] **Step 1: Write failing tests** `tests/test_notification_generation_api.py`:

```python
"""Tests for the notification generation and reset API actions."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from users.models import ObjectPermission

from notices.models import NotificationTemplate, PreparedNotification

User = get_user_model()


@pytest.fixture
def kind():
    return NotificationTemplate.objects.create(
        name="NOC", slug="noc", event_type="maintenance", granularity="per_event",
        subject_template="S", body_template="B", body_format="text",
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_api():
    return _client(User.objects.create_superuser(username="api-admin", password="x", email="x@example.com"))


def _url(event):
    return f"/api/plugins/notices/maintenance/{event.pk}/generate-notifications/"


@pytest.mark.django_db
class TestGenerateAction:
    def test_dry_run_returns_plan_without_writing(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        response = admin_api.post(_url(event), {"dry_run": True}, format="json")
        assert response.status_code == 200
        assert [i["action"] for i in response.data["items"]] == ["create"]
        assert PreparedNotification.objects.count() == 0

    def test_apply_returns_saved_ids(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        response = admin_api.post(_url(event), {}, format="json")
        assert response.data["counts"] == {"create": 1}
        assert response.data["items"][0]["notification"] == PreparedNotification.objects.get().pk

    def test_rejects_template_that_is_not_a_kind_for_event(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        outage_kind = NotificationTemplate.objects.create(
            name="O", slug="o", event_type="outage", subject_template="S", body_template="B"
        )
        response = admin_api.post(_url(event), {"templates": [outage_kind.pk]}, format="json")
        assert response.status_code == 400

    def test_needs_notification_permissions_not_event_add(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        user = User.objects.create_user(username="gen", password="x")
        perm = ObjectPermission.objects.create(
            name="gen", actions=["view", "add", "change", "delete"]
        )
        perm.object_types.add(*_content_types("preparednotification"))
        perm.users.add(user)
        view = ObjectPermission.objects.create(name="view-maint", actions=["view"])
        view.object_types.add(*_content_types("maintenance"))
        view.users.add(user)
        assert _client(user).post(_url(event), {"dry_run": True}, format="json").status_code == 200

    def test_without_notification_permissions_is_forbidden(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        user = User.objects.create_user(username="viewer", password="x")
        view = ObjectPermission.objects.create(name="view-maint2", actions=["view"])
        view.object_types.add(*_content_types("maintenance"))
        view.users.add(user)
        assert _client(user).post(_url(event), {"dry_run": True}, format="json").status_code == 403


def _content_types(model):
    from core.models import ObjectType

    return [ObjectType.objects.get(app_label="notices", model=model)]


@pytest.mark.django_db
class TestResetAction:
    def test_reset_returns_unmodified_notification(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        admin_api.post(_url(event), {}, format="json")
        n = PreparedNotification.objects.get()
        n.body_text = "edited"
        n.save()
        response = admin_api.post(f"/api/plugins/notices/prepared-notifications/{n.pk}/reset/")
        assert response.status_code == 200
        assert response.data["modified"] is False and response.data["body_text"] == "B"

    def test_reset_non_draft_is_400(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        admin_api.post(_url(event), {}, format="json")
        PreparedNotification.objects.update(status="sent")
        n = PreparedNotification.objects.get()
        assert admin_api.post(f"/api/plugins/notices/prepared-notifications/{n.pk}/reset/").status_code == 400
```

- [ ] **Step 2: Run** `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/test_notification_generation_api.py -q` -- expect 404s.

- [ ] **Step 3: Serializers** in `notices/api/serializers/messaging.py`:

```python
class GenerateNotificationsSerializer(serializers.Serializer):
    templates = serializers.PrimaryKeyRelatedField(queryset=NotificationTemplate.objects.all(), many=True, required=False)
    dry_run = serializers.BooleanField(default=False)

    def validate_templates(self, value):
        kinds = set(self.context["kinds"])
        invalid = [t.pk for t in value if t not in kinds]
        if invalid:
            raise serializers.ValidationError(f"Not a notification kind for this event: {invalid}")
        return value


class PlannedNotificationSerializer(serializers.Serializer):
    action = serializers.CharField()
    template = serializers.SerializerMethodField()
    root_template = serializers.IntegerField(source="root_template.pk")
    tenant = serializers.SerializerMethodField()
    impact = serializers.SerializerMethodField()
    contacts = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    error = serializers.CharField(allow_null=True)
    notification = serializers.SerializerMethodField()

    def get_template(self, obj):
        return getattr(obj.template, "pk", None)

    def get_tenant(self, obj):
        return getattr(obj.tenant, "pk", None)

    def get_impact(self, obj):
        return getattr(obj.impact, "pk", None)

    def get_contacts(self, obj):
        return [c.pk for c in obj.contacts]

    def get_subject(self, obj):
        return obj.content.get("subject") or getattr(obj.existing, "subject", None)

    def get_notification(self, obj):
        return getattr(obj.notification or obj.existing, "pk", None)
```

Add to `PreparedNotificationSerializer`: `tenant = serializers.PrimaryKeyRelatedField(read_only=True)`, `impact = serializers.PrimaryKeyRelatedField(read_only=True)`, `modified = serializers.BooleanField(source="is_modified", read_only=True)`; list them in `Meta.fields` after `event_id`. Export new serializers from `notices/api/serializers/__init__.py`.

- [ ] **Step 4: Actions.** In `notices/api/views/events.py` add one mixin used by both viewsets:

```python
from django.shortcuts import get_object_or_404
from netbox.api.authentication import TokenWritePermission  # verify name/behaviour; see note
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

GENERATE_PERMISSIONS = (
    "notices.add_preparednotification",
    "notices.change_preparednotification",
    "notices.delete_preparednotification",
)


class GenerateNotificationsMixin:
    """`generate-notifications` action shared by the Maintenance and Outage viewsets."""

    @action(detail=True, methods=["post"], url_path="generate-notifications", permission_classes=[...])
    def generate_notifications(self, request, pk=None):
        if not request.user.has_perms(GENERATE_PERMISSIONS):
            raise PermissionDenied("Generating notifications requires add, change and delete on prepared notifications.")
        event = get_object_or_404(self.queryset.model.objects.restrict(request.user, "view"), pk=pk)
        generator = NotificationGenerator(event)
        params = GenerateNotificationsSerializer(data=request.data, context={"kinds": generator.applicable_kinds()})
        params.is_valid(raise_exception=True)
        if params.validated_data.get("templates"):
            generator = NotificationGenerator(event, templates=params.validated_data["templates"])
        plan = generator.plan()
        if params.validated_data["dry_run"]:
            counts = Counter(item.action for item in plan)
            result = GenerationResult(items=plan, counts=dict(counts))
        else:
            result = generator.apply(plan)
        return Response({
            "summary": result.summary(),
            "counts": result.counts,
            "items": PlannedNotificationSerializer(result.items, many=True).data,
        })
```

Permission note: NetBox's default `TokenPermissions` maps POST to the viewset model's `add` permission (here `add_maintenance`), and `BaseViewSet.initial()` restricts `self.queryset` by `add`. Neither fits this action. Set `permission_classes` on the action to `[IsAuthenticatedOrLoginNotRequired]` plus whatever NetBox class enforces token write-ability for unsafe methods (read `/opt/netbox/netbox/netbox/api/authentication.py` -- `TokenWritePermission` exists there; check whether it tolerates session/force_authenticate clients, since tests use `force_authenticate`), then do the explicit `has_perms` check above and look the event up with a fresh `restrict(request.user, "view")` queryset (as shown) rather than `self.get_object()`. The two permission tests in Step 1 pin this behaviour. Make dry-run counting DRY: add a `GenerationResult.from_plan(plan)` classmethod in Task 5's module (counts only) and use it here and in `apply`.

`MaintenanceViewSet(GenerateNotificationsMixin, NetBoxModelViewSet)`, `OutageViewSet(GenerateNotificationsMixin, NetBoxModelViewSet)`.

In `notices/api/views/messaging.py` `PreparedNotificationViewSet`:

```python
    @action(detail=True, methods=["post"], permission_classes=[...same as above...])
    def reset(self, request, pk=None):
        if not request.user.has_perm("notices.change_preparednotification"):
            raise PermissionDenied()
        notification = get_object_or_404(PreparedNotification.objects.restrict(request.user, "change"), pk=pk)
        try:
            NotificationGenerator(notification.event).reset(notification)
        except (ValueError, TemplateRenderError) as e:
            raise ValidationError({"detail": str(e)})
        return Response(self.get_serializer(notification).data)
```

(`notification.event` is None for hand-created ones -- `NotificationGenerator(None).reset` must raise ValueError before touching the event; make sure Task 5's `reset` checks `notification.event` first.)

- [ ] **Step 5: Run** Step 2 command plus `tests/test_messaging_api.py`. Expected PASS.

- [ ] **Step 6: Lint and commit**

```bash
git add notices/api/ notices/services/notification_generation.py tests/test_notification_generation_api.py
git commit -m "feat(api): add generate-notifications and reset actions"
```

---

### Task 9: Opt-in automatic generation

**Files:**
- Modify: `notices/__init__.py` (default setting)
- Create: `notices/auto_generation.py`
- Modify: `notices/signals.py` (wire receivers)
- Test: `tests/test_auto_generation.py`

**Interfaces:**
- Consumes: Task 5 `NotificationGenerator`.
- Produces: setting `auto_generate_notifications` (dict `{"maintenance": [statuses], "outage": [statuses]}`, default `{"maintenance": [], "outage": []}`); `notices.auto_generation.schedule_generation(event)`, `is_meaningful_event_change(instance, created) -> bool`, `auto_statuses(event) -> list[str]`.

- [ ] **Step 1: Write failing tests** `tests/test_auto_generation.py`:

```python
"""Tests for opt-in automatic notification generation."""

from unittest import mock

import pytest
from django.db import transaction

from notices import auto_generation
from notices.models import Impact, NotificationTemplate, PreparedNotification

SETTING = "notices.auto_generation.auto_statuses"


@pytest.fixture
def kind():
    return NotificationTemplate.objects.create(
        name="NOC", slug="noc", event_type="maintenance", granularity="per_event",
        subject_template="S {{ maintenance.status }}", body_template="B", body_format="text",
    )


@pytest.mark.django_db(transaction=True)
class TestAutoGeneration:
    def test_off_by_default(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        event.snapshot()
        event.status = "TENTATIVE"
        event.save()
        assert PreparedNotification.objects.count() == 0

    def test_status_change_into_configured_status_generates(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        with mock.patch(SETTING, return_value=["CANCELLED"]):
            event.snapshot()
            event.status = "CANCELLED"
            event.save()
        assert PreparedNotification.objects.get().subject == "S CANCELLED"

    def test_trivial_change_does_not_generate(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        with mock.patch(SETTING, return_value=["CONFIRMED"]):
            event.snapshot()
            event.comments = "note"
            event.save()
        assert PreparedNotification.objects.count() == 0

    def test_one_run_per_transaction(self, maintenance_with_two_tenants, kind, site):
        event, *_ = maintenance_with_two_tenants
        with mock.patch(SETTING, return_value=["CONFIRMED"]), mock.patch.object(
            auto_generation, "run_generation", wraps=auto_generation.run_generation
        ) as run:
            with transaction.atomic():
                event.snapshot()
                event.start = event.start.replace(microsecond=0)  # meaningful only if it differs
                event.end = event.end + __import__("datetime").timedelta(hours=1)
                event.save()
                Impact.objects.create(event=event, target=site, impact="DEGRADED")
            assert run.call_count == 1

    def test_failure_is_journaled_and_does_not_break_save(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        kind.body_template = "{% if %}"
        kind.save()
        with mock.patch(SETTING, return_value=["CANCELLED"]):
            event.snapshot()
            event.status = "CANCELLED"
            event.save()
        assert event.journal_entries.filter(kind="warning").exists()
```

(`transaction=True` is required so `on_commit` callbacks fire. If `journal_entries` is not the accessor name on NetBox models, query `JournalEntry.objects.filter(assigned_object_id=event.pk)`.)

- [ ] **Step 2: Run** `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/test_auto_generation.py -q` -- expect ImportError.

- [ ] **Step 3: Implement** `notices/auto_generation.py`:

```python
"""
Opt-in automatic generation of draft notifications when an event changes meaningfully.

Runs after the surrounding transaction commits, at most once per event per transaction, and
never lets a generation failure break the save that triggered it.
"""

import logging
import threading

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from netbox.config import get_config

logger = logging.getLogger("notices.auto_generation")

# Event fields whose change warrants telling customers again.
MEANINGFUL_FIELDS = ("status", "start", "end", "estimated_time_to_repair")

_pending = threading.local()


def auto_statuses(event):
    setting = get_config().PLUGINS_CONFIG.get("notices", {}).get("auto_generate_notifications") or {}
    return setting.get(event._meta.model_name, [])


def is_meaningful_event_change(instance, created):
    if created:
        return True
    before = getattr(instance, "_prechange_snapshot", None)
    if not before:
        # Saved outside NetBox's change logging (no snapshot): we cannot tell, so assume it matters.
        return True
    after = instance.serialize_object()
    return any(before.get(name) != after.get(name) for name in MEANINGFUL_FIELDS)


def schedule_generation(event):
    """Queue one generation run for this event after the current transaction commits."""
    if event is None or not auto_statuses(event):
        return
    key = (ContentType.objects.get_for_model(event).pk, event.pk)
    pending = getattr(_pending, "keys", None)
    if pending is None:
        pending = _pending.keys = set()
    if key in pending:
        return
    pending.add(key)
    transaction.on_commit(lambda: _run_pending(key, type(event)))


def _run_pending(key, model):
    _pending.keys.discard(key)
    event = model.objects.filter(pk=key[1]).first()
    if event is not None and event.status in auto_statuses(event):
        run_generation(event)


def run_generation(event):
    from extras.models import JournalEntry

    from notices.choices import GenerationActionChoices
    from notices.services.notification_generation import NotificationGenerator

    try:
        generator = NotificationGenerator(event)
        result = generator.apply(generator.plan())
        errors = [item.error for item in result.items if item.action == GenerationActionChoices.ERROR]
    except Exception as e:  # never break the save that triggered us
        logger.exception("Automatic notification generation failed for %s", event)
        errors = [str(e)]
    if errors:
        JournalEntry.objects.create(
            assigned_object=event,
            kind="warning",
            comments="Automatic notification generation failed:\n\n" + "\n".join(f"- {e}" for e in errors),
        )
```

`Outage.end`/`estimated_time_to_repair` and `Maintenance` lacking ETR are fine: `.get()` returns None on both sides.

In `notices/signals.py` add:

```python
from .auto_generation import is_meaningful_event_change, schedule_generation


@receiver(post_save, sender=Maintenance)
@receiver(post_save, sender=Outage)
def _auto_generate_on_event_save(sender, instance, created, **kwargs):
    if is_meaningful_event_change(instance, created):
        schedule_generation(instance)


@receiver(post_save, sender=Impact)
@receiver(post_delete, sender=Impact)
def _auto_generate_on_impact_change(sender, instance, **kwargs):
    schedule_generation(instance.event)
```

(import `Outage` from `.models`). In `notices/__init__.py` `default_settings` add `"auto_generate_notifications": {"maintenance": [], "outage": []},`.

- [ ] **Step 4: Run** Step 2 command, then the full suite (signals affect every event save): `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest --no-cov -p no:cacheprovider tests/ -q`. Expected PASS.

- [ ] **Step 5: Lint and commit**

```bash
git add notices/auto_generation.py notices/signals.py notices/__init__.py tests/test_auto_generation.py
git commit -m "feat(signals): opt-in automatic notification generation"
```

---

### Task 10: Documentation

**Files:**
- Modify: `README.md`, `CHANGELOG.md`, `docs/outgoing-notifications.md`, `docs/messaging/templates.md`, `docs/messaging/workflow.md`, `docs/configuration.md`, `docs/api/rest-api.md`, `docs/permissions.md`

- [ ] **Step 1: CHANGELOG** under `## [Unreleased]` (create the heading if missing; Keep-a-Changelog):

```markdown
### Added
- Generate outgoing notifications from a maintenance or outage: "Generate Notifications" in the event's Operations menu (with preview), `POST /api/plugins/notices/{maintenance,outage}/{id}/generate-notifications/` (with `dry_run`), and opt-in automatic generation via `auto_generate_notifications`.
- Regeneration re-renders untouched drafts in place and keeps hand-edited drafts and anything already approved or sent.
- "Reset to template" for hand-edited drafts (UI and `POST .../prepared-notifications/{id}/reset/`), and "Approve" in the UI.
- Prepared notifications record their recipient group (`tenant`, `impact`) and expose a `modified` flag, filterable in the list and API.
- Outgoing notifications appear on the event timeline.

### Changed
- Template matching: every non-base template is an independent notification kind; a template that extends a non-base template overrides it for the recipient groups its scopes match. Fields merge only along the `extends` chain instead of across every matching template. `{% extends "base" %}` now renders with the full context and resolves to the template's own parent.
- An override must use the same granularity as the template it extends, and `extends` cycles are rejected on save.
```

- [ ] **Step 2: Docs pages.**
  - `docs/outgoing-notifications.md`: add a "Generating notifications" section (UI flow, API action with request/response example, auto mode) and a "Regeneration" table (create/update/keep/delete/skip/error with one-line meaning each); make the flow diagram's render step name `NotificationGenerator`.
  - `docs/messaging/templates.md`: replace the matching/merging section with kinds, overrides, base templates as layouts, score = weight + matching scope weights, chain merge; document `{% extends "base" %}` resolution (immediate parent at every level); document `body_format` handling (markdown/html/text -> body_text/body_html); remove the "no cycle check" caveat.
  - `docs/messaging/workflow.md`: Approve button, Reset to template, modified flag and its limitation (recipient-only edits are not detected).
  - `docs/configuration.md`: `auto_generate_notifications` with an example and the "meaningful change" definition (created; status/start/end/ETR changed; impact added/changed/removed), run-after-commit and once-per-transaction behaviour, journaled failures, and the note that runs outside a request do not appear on the timeline.
  - `docs/api/rest-api.md`: both actions with curl examples.
  - `docs/permissions.md`: generation needs add+change+delete on prepared notifications plus view on the event; approve/reset need change.
  - `README.md`: one feature bullet for outgoing notification generation.
- [ ] **Step 3: ASCII check**: `grep -nP '[^\x00-\x7F]' CHANGELOG.md README.md docs/outgoing-notifications.md docs/messaging/*.md docs/configuration.md docs/api/rest-api.md docs/permissions.md` -- any hit in lines you wrote must be fixed.
- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md docs/
git commit -m "docs: document outgoing notification generation"
```

---

## Final verification (after Task 10)

- Full suite with coverage: `flock /tmp/netbox-plugins-testdb.lock /opt/netbox/venv/bin/python -m pytest -p no:cacheprovider tests/ --cov=notices --cov-report=xml -q`
- Diff coverage: `uvx diff-cover coverage.xml --compare-branch origin/main` -- changed-line coverage at or above the project average (about 83%).
- `ruff check notices/ tests/` and `ruff format --check notices/ tests/` clean.
- DRY review subagent (Fable) on `git diff origin/main...HEAD`, findings reported to the user before any PR.
