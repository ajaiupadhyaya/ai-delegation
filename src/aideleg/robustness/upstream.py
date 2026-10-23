"""The one door from Plan 4 to Plan 2 and Plan 3 code.

Task 1 re-exports Plan 3's confirmatory-record guard only; Task 2 completes the adapter.
"""

from aideleg.rq3.guard import ConfirmatoryNotRecorded, assert_confirmatory_recorded

__all__ = ["ConfirmatoryNotRecorded", "assert_confirmatory_recorded"]
