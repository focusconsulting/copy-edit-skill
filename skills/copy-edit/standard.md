# Editorial standard

The rule for every human-language artifact in a repository — code
comments, docstrings, template comments, ADRs, PRDs: say only what the
artifact itself cannot. Prose is edited like copy, not accumulated
like sediment. Every explanation gets one home; every other site
references it or stays silent.

The `copy-edit` skill and `copy-editor` agent apply this file as
written.

## Keep

Text that carries one of these earns its place, compressed if bloated:

- **why** — the reason for a non-obvious choice.
- **constraint** — an external requirement the code must satisfy: a
  spec value, a legal rule, an API contract.
- **invariant** — a property the code relies on but does not check.
- **gotcha** — behavior that will surprise a competent reader.
- **regression record** — the bug a test or guard exists to prevent.
- **external source with removal condition** — where a workaround came
  from and when it can die.
- **direction of error** — which way an approximation is biased, and
  why that direction is safe.

## Delete

- **restatement** — repeats the name, signature, types, or visible
  control flow.
- **banner** — `# ---- section ----` dividers. Extract a function, use
  a class, or delete.
- **narration** — step-by-step commentary on the next line.
- **history** — what the code used to do, or how this diff evolved.
  That is the commit message's job.
- **duplicate home** — a second telling of an explanation that already
  lives elsewhere. Keep the one home; point to it or cut.
- **reviewer-directed** — argument that the change is correct,
  addressed to the PR reviewer. Belongs in the PR description; it is
  noise the day after merge.
- **dead prose** — TODOs with no owner or trigger condition,
  commented-out code, references that cannot stay current.

## Compress

- **over-argued why** — right content, three times the words. Keep the
  payload sentence; cut the argument, the hedges, and the restated
  context.
- **filler** — "it should be noted that", "importantly", "in order
  to", "note that", "this ensures". Delete the scaffolding, keep the
  claim.

## Citation density

Cite an external authority — spec section, bulletin, upstream issue —
once, at the point where its value or rule is transcribed: the
constant, the predicate, the ADR decision. Downstream code references
the named constant or function, not the citation. Plans and ADRs still
link their specs; code cites where it transcribes.

## Em dashes

The character is legal: a single set-off clause is punctuation. The
tic is density. If a comma or period serves, use it; rewrite any
comment paragraph with two or more.

## Placement

An explanation lives at the most local site that covers all its
readers: test comment, then function comment, then module docstring,
then ADR. Other sites reference it, never restate it.

## Defaults

When unsure, compress; don't delete. Never delete text that names a
bug, a bias direction, an invariant, an external document, or a
removal condition.

## Before and after

Anonymized from real diffs.

**Restatement — delete.** The signature already says all of it:

```python
def _monthly_income(answers: Answers) -> int | None:
    """The submitted monthly income as a whole-dollar int. ``None`` if unanswered
    or unreadable."""
    return answer_int(answers, "income")
```

```python
def _monthly_income(answers: Answers) -> int | None:
    return answer_int(answers, "income")
```

**Over-argued — compress.** A 26-line module docstring recapping the
pricing document section by section:

```python
"""Shipping quote — the checkout's shipping charge for a cart.

This is the module which computes the shipping charge. It resolves two
paths today:

- **Flat rate (pricing doc §2.1):** a cart that qualifies outright — a
  member account, a promotional code, or an order over the free-shipping
  threshold — ships at the flat rate. …
"""
```

becomes a docstring that states the shape, the invariant, and the
boundary:

```python
"""Shipping charge for a cart.

Two paths: flat rate (pricing doc §2.1), else the weight table (§2.3);
a size cap (§2.5) can then refuse the order. Missing dimensions never
refuse an order. Cart facts come from ``cart``, which owns validation;
this module owns the charge.
"""
```

**Keep as-is.** High comment-to-code ratio is not the test. This
docstring names the broken version, the exact failure, and its removal
condition — nothing to cut:

```python
"""``JSONEncoder`` that writes ``Decimal`` as ``str``.

billing-sdk 2.4.0 returns ``Decimal`` amounts from ``list_invoices()``.
The report writer passes them to ``json.dumps``, which raises
``TypeError``. Remove once fixed upstream.
"""
```

**Narration and banners — delete.**

```ts
await next(page); // -> shipping
await next(page); // -> payment
```

```python
# ---- helpers ----
```

The step titles and function names already tell the story; the banner
marks a section that a class or a blank line marks better.

## Out of scope

- ADR format idioms: the `# ADR NNN — Title` heading and
  `rejected — reason` lines.
- End-to-end test titles written for non-technical reviewers. Length
  there is a feature.
- License and encoding headers.
