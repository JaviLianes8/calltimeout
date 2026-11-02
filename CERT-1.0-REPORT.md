# calltimeout 1.0.0 certification report

The 1.0.0 certification bar (19 items) applied to calltimeout. The PyPI JSON endpoint (`https://pypi.org/pypi/calltimeout/json`) returned 200 on 2026-11-02: 0.2.0 was published on 2026-10-31.
Every module and `py.typed` in that wheel matches `main` at 9b6975c (line endings normalized). The CHANGELOG therefore describes changes against the actual published release.
It previously returned 404 on 2026-10-18, 2026-10-22, 2026-10-25 and 2026-10-26; those observations predate the publication.

Progress:
- [x] Branch `release/1.0.0` created from `main` (9b6975c, 0.2.0)
- [x] Baseline gates on 0.2.0
- [x] API review and 1.0.0 changes (item 1)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Ground truth: documentation fetched live, pebble run live (item 7)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [x] Packaging, e2e, every Python (items 8, 10, 13, 14)
- [x] Gates (item 15)
- [x] PR and trace guard
- [x] Five QA lenses, round 1: every finding fixed (3309979)
- [x] Five QA lenses, round 2: every finding fixed (00f6889, 6e2c03c)
- [x] Five QA lenses, round 3: every finding fixed (2f962f3 to db26ef1)
- [x] Five QA lenses, round 4: every finding fixed (726f948 to 388e62b)
- [x] Lens e, round 5: every surviving mutant pinned or shown equivalent (9f00374, 5b84b46)
- [x] Five QA lenses, round 6: every finding fixed (f477ccf, 3220523)
- [x] Five QA lenses, round 7: every finding fixed (88d5474 to 05d15a6)
- [x] Five QA lenses, round 8: every finding fixed (052f156 to be35644)
- [x] Current QA round 1: nine findings fixed in dfd6ba4 (2026-11-02)
- [x] Current QA round 2: C-06 fixed in 75cb060 (2026-11-02)
- [x] Current QA round 3: C-07 fixed in 33271de (2026-11-02)
- [x] Current QA round 4: C-08 fixed in 8aa8992 (2026-11-02)
- [x] Current QA round 5: C-09 fixed in ac2da71 (2026-11-02)
- [ ] Five QA lenses re-verified (item 19) and independent reviewer (item 16)
- [x] PyPI 0.2.0 installed and upgraded in place to the built 1.0.0 wheel (2026-11-02)
- [x] Current laptop interpreter matrix and mutation verification (2026-11-02)

## Scorecard

| # | Item | Result |
| --- | --- | --- |
| 1 | Public API reviewed for stability | PASS: the five names of 0.2.0 kept with their parameter names and defaults, and `RemoteTraceback` added (QA round 7), pinned by `tests/test_contract_api.py`; every behaviour change in the CHANGELOG and the GUIDE |
| 2 | `__all__` exact, no private imports in docs | PASS: `CallCrashed`, `CallTimeout`, `Mode`, `RemoteTraceback`, `run`, `with_timeout`; `tests/test_contract.py` |
| 3 | Docstrings with runnable examples, doctests | PASS: every public name has a doctest (6, also run from the installed wheel; `Mode`'s section of the package docstring is run by `tests/test_contract.py`, since a docstring on the cached `Literal` would relabel the caller's identical aliases); README and GUIDE examples run as scripts by the tests with their printed output checked |
| 4 | Typed end to end | PASS: `mypy --strict src tests` for the Windows, Linux and macOS platforms; `py.typed` shipped; a consumer script type-checked against the installed wheel |
| 5 | Typed, documented, bounded errors | PASS: fixed validation messages, value-free transport causes and documented scope for propagated callable exceptions; current QA round 1 below |
| 6 | Contract tests of every public name | PASS |
| 7 | Real ground truth | PASS: 8 CPython and PEP documents fetched with a hash manifest, each fact checked against the running interpreter; pebble 5.2.3 run live as a second implementation |
| 8 | Real e2e from the wheel | PASS: wheel and sdist built, inspected, installed in throwaway venvs and used from an empty folder; no CLI; PyPI 0.2.0 upgraded in place on 2026-11-02 |
| 9 | Seeded fuzz, no crash, hang or blowup | PASS |
| 10 | Supported Pythons | PASS: twelve local CPython builds from 3.10 to 3.14, including free-threaded 3.14.10; see the installed-wheel matrix below |
| 11 | README and `twine check` | PASS: `twine check --strict` in the e2e tests, absolute links, problem, why versus five alternatives checked on PyPI on 2026-10-22, certified badge |
| 12 | Dated CHANGELOG section | PASS: `## [1.0.0] - 2026-11-02` |
| 13 | pyproject 1.0.0, Production/Stable | PASS: 3.10 to 3.14, CPython, MIT, Homepage/Source/Issues/Changelog, keywords, `dependencies = []` |
| 14 | sdist and wheel contents | PASS: asserted by `tests/test_e2e_wheel.py` |
| 15 | Gates each exit 0 | PASS: see current QA round 5 and Preparation verification below |
| 16 | Independent reviewer | pending |
| 17 | PR and trace guard | PR #3 from `release/1.0.0`, trace guard CLEAN; merge and publish left to the maintainer |
| 18 | Contracts bite (mutations) | PASS: original 58-mutant round retained in the linked table; ten mutations applied to the current source on 2026-11-02, all killed (table below) |
| 19 | Five independent QA lenses | Rounds 1 to 4: every finding of the five lenses fixed, at 3309979, at 00f6889 and 6e2c03c, at 2f962f3 to db26ef1, and at 726f948 to 388e62b; round 5: lens e's survivors pinned in 9f00374 and 5b84b46; round 6: every finding fixed in f477ccf and 3220523; round 7: every finding fixed in 88d5474 to 05d15a6; round 8: every finding fixed in 052f156 to be35644 (see QA lenses); re-verification pending |

## QA lenses, 2026-11-02 round 1

Baseline: `8693a159f551806d479ab3313fd5c9df6cfdf84a`.
Fix commit: `dfd6ba4203b51385d3def3d3ce5c5a79c6c5cd36`.

| Finding | Change and contract |
| --- | --- |
| A1 | Reject negative real values before float underflow; both public entry points tested. |
| A2, C-01 | Conversion errors retain no original text, notes, cause or context; million-character errors tested. |
| A3 | CHANGELOG, GUIDE and run docstring state that validation and keyword copying precede the budget. |
| B-001 | Only a decorator's own child receives one-use wrapper bypass; generic process calls preserve inner deadlines, defaults and zero-budget no-call behavior. |
| C-02 | Mapping iteration and lookup failures become safe TypeErrors, including at zero budget. |
| C-03 | Guarded actual-type checks avoid hostile __class__ properties and preserve genuine subclasses and ABC registrations. |
| C-04 | Invalid modes and all four transport directions omit caller text; transport causes discard notes, frames and chains without editing the original error. |
| C-05 | Normalize string keys before insertion; collision contracts check operation counts and one read per value. |

All nine findings are fixed; none disputed. Independent re-verification remains pending. The 22 new contract cases all failed on the baseline before implementation and now pass.
Reviewer repros rerun against the fix: A1/A2, 3 passed; B-001, 3 passed; C validation and scaling, 11 passed, with zero key comparisons at 500 through 4,000 colliding keys.
Windows CPython 3.14.6: ruff format --check ., ruff check ., mypy --strict src and pytest each exited 0; pytest: 405 passed, 53 skipped, with a 300-second per-test timeout and scratch basetemp. mypy --strict src tests also passed.
POSIX and optional packaging checks were not rerun in this fix pass; their earlier evidence is retained below.

## QA lenses, 2026-11-02 round 2

Baseline: `75d143a908562133f0b1a21acef0cc5391500e35`. Fix commit: `75cb060fa2001c3c3c4a21c54dc65ef6dfd658d5`.

C-06 (medium): exact built-in keyword dictionaries now yield stored key/value pairs, avoiding repeated source lookups for colliding string-subclass keys. Destination keys are normalized; custom mapping reads and validation order retain their semantics.
Four new contract cases first failed with 124,750 and 7,998,000 equality calls for 500 and 4,000 keys, at zero and positive budgets. All now pass with zero comparisons, preserved values and source contents, plain-string destination keys, and no zero-budget call.
Targeted contracts: 76 passed. Reviewer validation probes: 24 passed, zero comparisons at 500, 1,000, 2,000 and 4,000 keys; the 4,000-key validation took 0.001653 seconds.
Windows CPython 3.14.6: all four gates exited 0; pytest: 409 passed, 53 skipped, 300-second per-test timeout and scratch basetemp. Strict typing of tests also passed.
C-06 is fixed; none disputed. Independent re-verification remains pending.

## QA lenses, 2026-11-02 round 3

Baseline: `aa01295726b16b33efa3f1b03f8c5072a5159390`. Fix commit: `33271de7469c43e8609cf34ad4bcd68572fd5c29`.

C-07 (medium): keyword dictionary subclasses with inherited reads and dictionary-backed proxies now use stored pairs without repeated source lookups. Proxy backing mappings are identified through CPython GC traversal, with ordinary mapping reads as the fallback. Custom key selection, value lookup and validation order are preserved, including instance overrides and nested proxies. Destination keys remain plain strings; source keys and values are unchanged.
Eight new collision contracts first failed on the baseline with 124,750 and 7,998,000 comparisons at 500 and 4,000 keys, at zero and positive budgets. They now require zero comparisons, preserved values and no zero-budget call. Another 30 cases cover custom mapping behavior, hidden instance and class namespaces, inherited subclasses, nested proxies and keys whose hash becomes unusable after dictionary construction.
The original reviewer harness passes all 40 probes, including zero comparisons for both wrappers at 500, 1,000, 2,000 and 4,000 keys. The public API is unchanged and the behavior change is recorded in CHANGELOG.
Windows CPython 3.14.6: ruff format --check ., ruff check ., mypy --strict src and pytest each exited 0; pytest: 447 passed, 53 skipped, with a 300-second per-test timeout and scratch basetemp. Strict typing of tests also passed. POSIX, optional packaging and the interpreter matrix were not rerun in this fix pass; their earlier evidence is retained below.
C-07 is fixed; none disputed. Independent re-verification remains pending.

## QA lenses, 2026-11-02 round 4

Baseline: `1afe973e4a6fb239fad13ffaecd02c0b4e746052`. Fix commit: `8aa899233526e29c4ce8f6330d9e1aae88a874d2`.

C-08 (medium): stored-pair copying now requires the instance namespace descriptor to have the expected name and belong to the class that defines it in the MRO. Aliased or shadowed descriptors use ordinary mapping reads, preserving instance `keys()` selection directly and through nested proxies. The public API is unchanged; CHANGELOG records the behavior change.
Three new public contract cases first failed on the baseline, passing the excluded `other` keyword at proxy depths 0, 1 and 2. All now pass and verify the source dictionary is unchanged. Targeted contracts: 60 passed, including the C-07 collision checks.
Reviewer confirmation and robustness probes: 43 passed, including C-07 and C-08. Windows CPython 3.14.6: ruff format --check ., ruff check ., mypy --strict src and pytest each exited 0; pytest: 450 passed, 53 skipped, with a 300-second per-test timeout and scratch basetemp. Strict typing of tests also passed. POSIX, optional packaging and the interpreter matrix were not rerun in this fix pass; their earlier evidence is retained below.
C-08 is fixed; none disputed. Independent re-verification remains pending.

## QA lenses, 2026-11-02 round 5

Baseline: `dc4838bcd211d9855a8ba94a067fd4401a18e7e6`. Fix commit: `ac2da718d7f1749ded921e10e96c554e50e3bd39`.

C-09 (medium): aliased dictionary namespace descriptors now permit stored-pair copying when mapping reads are unmodified. A verified built-in descriptor exposes the real instance namespace before class methods are checked, preserving C-08's instance key selection. Shadowed or foreign descriptors retain ordinary mapping reads. Public names and signatures are unchanged; CHANGELOG records the behavior change.
All 24 new contract cases first failed with 2,016 or 32,640 equality calls at 64 and 256 keys. They now require zero comparisons and zero rehashes, preserved source and value identities, plain-string destination keys and zero-budget no-call behavior. Cases cover proxy depths 0, 1 and 3, with empty namespaces or unrelated instance attributes. Targeted validation contracts: 84 passed; final keyword contracts: 57 passed.
The independent reviewer harness passes all 39 probes, including C-08 selection, descriptor variants, seeded selection, malformed keys and collision scaling. At 4,000 keys, direct and nested-proxy aliases each perform zero comparisons; median public call times were 0.010200 and 0.010969 seconds, respectively.
Windows CPython 3.14.6: ruff format --check ., ruff check ., mypy --strict src and pytest each exited 0; pytest: 474 passed, 53 skipped, with a 300-second per-test timeout and scratch basetemp. Strict typing of tests also passed. POSIX, optional packaging and the interpreter matrix were not rerun in this fix pass; their earlier evidence is retained below.
C-09 is fixed; none disputed. Independent re-verification remains pending.

## Earlier evidence and QA lenses

The earlier evidence is retained in full, separated by round for readability. Dates and machine names in these records refer to those historical runs. No round records a final pass of all five lenses; re-verification remains pending.

- [Baseline, API review, ground truth, fuzz, packaging and gates](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-BASELINE.md).
- [Original 58-mutation table](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-MUTATIONS.md).
- [QA round 1: findings, fixes and verification](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-QA-ROUND1.md).
- [QA round 2: findings, fixes and verification](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-QA-ROUND2.md).
- [QA round 3: findings, fixes and verification](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-QA-ROUND3.md).
- [QA round 4: findings, fixes and verification](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-QA-ROUND4.md).
- [QA round 5: findings, fixes and verification](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-QA-ROUND5.md).
- [QA round 6: findings, fixes and verification](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-QA-ROUND6.md).
- [QA round 7: findings, fixes and verification](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-QA-ROUND7.md).
- [QA round 8: findings, fixes and verification](https://github.com/JaviLianes8/calltimeout/blob/main/CERT-1.0-QA-ROUND8.md).

There are no disputed findings in rounds 1 to 8.

## Preparation verification, 2026-11-02

Resumed at d30aa43 with a clean working tree. The earlier QA findings, fixes and verification above are preserved. No runtime code changed in this preparation pass. Re-verification of the five lenses and the independent review remain pending.

- The installed 0.2.0 wheel was downloaded from PyPI and compared with `main`, as above. The published version had appeared since the last check; the CHANGELOG now records its publication date and dates 1.0.0 to 2026-11-02.
- All eight documents were fetched again with `scripts/fetch_upstream.py`; their sizes and SHA-256 values match the tracked manifest. The existing ground-truth tests ran against that fetched text and pebble 5.2.3 on Windows CPython 3.14.6.
- The resumed suite with fetched documents, pebble and e2e enabled: 404 passed, 32 skipped, one failure. The wheel contents contract still listed the modules from before round 8; `_child.py` and `_timers.py` are now included in its exact inventory.
- Updated e2e suite (`CALLTIMEOUT_E2E=1`, `CALLTIMEOUT_E2E_PYPI=1`): six passed. Both archives are inspected and pass `twine check --strict`; both install in fresh venvs and run the external consumer. A separate venv installs PyPI 0.2.0, exercises seeded calls, exceptions, crash exit codes, context propagation and a process decorator, then upgrades to the built wheel. The outputs agree and exceptions pickled under 0.2.0 load under 1.0.0. The full 1.0.0 consumer also passes after that upgrade. There is no CLI or entry point.
- Each gate exits 0 on its own on Windows CPython 3.14.6: `ruff format --check .` (75 files), `ruff check .`, `mypy --strict src` (15 files), `mypy --strict src tests` (66 files), and `pytest` (387 passed, 51 skipped). This repository run skips the optional e2e and fetched-document tests; those run separately above and in the installed-wheel matrix below. Tool versions: ruff 0.17.3, mypy 2.4.1.
- `mypy --strict src tests` also passes with `--platform linux` and `--platform darwin`.

### Mutation verification on the current source

Ten mutations applied individually to a scratch copy of the current runtime source, CPython 3.14.6, on 2026-11-02. Each listed contract first passed without its mutation, then failed by assertion with the mutation; the source was restored after each run. These replay M01 to M10 against the latest code (M08 now changes the copied-key check). All ten were killed, with no timeout, collection failure or surviving mutation.

| Id | Mutation | Result | Contract that failed |
| --- | --- | --- | --- |
| M01 | a bool timeout accepted | killed | `test_fuzz_arguments.py::test_every_timeout_is_judged_by_the_documented_rules[1]` |
| M02 | negative check off by one | killed | `test_fuzz_arguments.py::test_every_timeout_is_judged_by_the_documented_rules[1]` |
| M03 | TIMEOUT_MAX itself refused | killed | `test_fuzz_arguments.py::test_every_timeout_is_judged_by_the_documented_rules[1]` |
| M04 | NaN check dropped | killed | `test_validation.py::test_the_decorator_rejects_bad_settings_when_applied[<lambda>1]` |
| M05 | negative zero retained | killed | `test_regressions.py::test_the_timeout_is_reported_as_the_validated_float` |
| M06 | coroutine function check dropped | killed | `test_upstream_threads.py::test_a_partial_of_a_coroutine_function_is_refused_without_its_arguments` |
| M07 | a list accepted as args | killed | `test_validation.py::test_rejects_args_that_are_not_a_tuple` |
| M08 | kwargs key check dropped | killed | `test_validation.py::test_rejects_kwargs_with_keys_that_are_not_strings` |
| M09 | str subclass mode used as given | killed | `test_hardening.py::test_a_str_subclass_mode_is_read_as_the_plain_name` |
| M10 | wrong error type for a non-str mode | killed | `test_fuzz_arguments.py::test_only_the_three_mode_names_are_accepted[1]` |

### Installed-wheel interpreter matrix

Windows, 2026-11-02. Every distinct available CPython build from 3.10 upward was tested locally. Each environment installs the wheel; its tests come from the sdist with `src` omitted, and package doctests run against the installed modules. The eight fetched documents, pebble 5.2.3 and mypy are present in every environment.

| CPython | Passed | Skipped | Result |
| --- | --- | --- | --- |
| 3.10.11 | 399 | 33 | PASS |
| 3.10.22 | 399 | 39 | PASS |
| 3.11.9 | 400 | 32 | PASS |
| 3.11.11 | 400 | 38 | PASS |
| 3.11.18 | 400 | 38 | PASS |
| 3.12.10 | 400 | 32 | PASS |
| 3.12.16 | 400 | 38 | PASS |
| 3.13.2 | 400 | 32 | PASS |
| 3.13.18 | 400 | 38 | PASS |
| 3.14.6 | 401 | 37 | PASS |
| 3.14.10 | 401 | 37 | PASS |
| 3.14.10t | 401 | 37 | PASS |

The `t` build runs with the GIL disabled, including after importing the test tools.
3.10.11, 3.11.9, 3.12.10 and 3.13.2 are isolated copies of embedded runtimes; their six optional packaging tests are excluded because those runtimes omit `venv`. Those six tests pass separately in a full runtime. Other skips are POSIX/fork-only contracts and exception-note features absent on older Pythons. Other builds skip the six opt-in packaging tests. Python 3.11.11 is the locally bundled Blender runtime. Stale launcher entries point to absent files; available duplicate copies of the same build are represented once. No Python 3.15 or POSIX interpreter is installed here; the earlier Linux results remain historical evidence, not new local verification.

### Final archives

The final archives were rebuilt after the documentation updates. Both contents checks, `twine check --strict` and the sdist's fresh-install consumer passed (four tests). The wheel is byte-identical to the one used in the upgrade and interpreter matrix.

- Wheel SHA-256: `ab614cc24fac75a69d1117347a0fcb83e5ea66f5067080235e4210ef236f9a7a`.
- Sdist SHA-256: `82ba06d22be37927f273e529ecd5bc19353d246739e1cfb819ccdbd3a43fbbe9`.
- All 69 Python source files are at most 200 lines. The earlier report sections are preserved verbatim in their linked files, each under 200 lines and excluded from both distributions. The main report retains the current mutation table.
- The README badge matches the reference exactly. PyPI metadata for the five README alternatives was fetched again on 2026-11-02; versions and release dates agree.

Preparation items 1 to 15 and 18 are complete. Items 16 and 19 await independent verification; item 17's merge and publication remain pending.
