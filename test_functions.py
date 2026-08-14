"""
Test suite for the RailPulse GenAI assistant.

Run: python test_functions.py

These tests check the deterministic, code-level logic (not the LLM's
behavior directly, which is inherently non-deterministic and can't be
"tested" the same way -- that's exactly why we built these guardrails
in Python in the first place).
"""

# Adjust this import to match wherever your functions actually live
# (e.g. if everything is still in test.py, use: from test import ...)
from functions import (
    clean_sql_response,
    validate_query_safety,
    detect_delay_unit,
    run_query,
)


def check(description, condition):
    """Tiny helper: prints PASS/FAIL instead of a raw crash on failure."""
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {description}")
    return condition


def test_clean_sql_response():
    print("\n--- clean_sql_response ---")
    results = []

    # Normal case: no markdown, nothing to clean
    results.append(check(
        "plain SQL is returned unchanged",
        clean_sql_response("SELECT AVG(x) FROM y") == "SELECT AVG(x) FROM y"
    ))

    # Preamble before SELECT should be stripped
    results.append(check(
        "text before SELECT is stripped",
        clean_sql_response("Here's the query: SELECT AVG(x) FROM y") == "SELECT AVG(x) FROM y"
    ))

    # Markdown code fences (both sides) should be stripped
    results.append(check(
        "markdown code fences are stripped",
        clean_sql_response("```sql\nSELECT AVG(x) FROM y```") == "SELECT AVG(x) FROM y"
    ))

    # No SELECT anywhere -> must raise, not return something silently wrong
    try:
        clean_sql_response("I cannot answer this question")
        results.append(check("raises ValueError when no SELECT is found", False))
    except ValueError:
        results.append(check("raises ValueError when no SELECT is found", True))

    return all(results)


def test_validate_query_safety():
    print("\n--- validate_query_safety ---")
    results = []

    # Legitimate query must pass through untouched
    try:
        validate_query_safety("SELECT * FROM stop_id_updated")
        results.append(check("legit query with 'updated' substring is NOT blocked", True))
    except ValueError:
        results.append(check("legit query with 'updated' substring is NOT blocked", False))

    # Case-insensitivity: lowercase dangerous keyword must still be caught
    try:
        validate_query_safety("delete from trips")
        results.append(check("lowercase 'delete' is blocked", False))
    except ValueError:
        results.append(check("lowercase 'delete' is blocked", True))

    # Each banned keyword, tested individually
    for keyword in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "EXEC"]:
        try:
            validate_query_safety(f"{keyword} something")
            results.append(check(f"'{keyword}' is blocked", False))
        except ValueError:
            results.append(check(f"'{keyword}' is blocked", True))

    return all(results)


def test_detect_delay_unit():
    print("\n--- detect_delay_unit ---")
    results = []

    results.append(check(
        "detects seconds when no division present",
        detect_delay_unit("SELECT AVG(departure_delay) FROM realtime_stop_updates") == "seconds"
    ))
    results.append(check(
        "detects minutes when '/ 60.0' is present",
        detect_delay_unit("SELECT AVG(departure_delay) / 60.0 FROM realtime_stop_updates") == "minutes"
    ))
    results.append(check(
        "detects minutes even without a decimal point ('/60')",
        detect_delay_unit("SELECT AVG(departure_delay)/60 FROM realtime_stop_updates") == "minutes"
    ))

    return all(results)


def test_security_guardrail_end_to_end():
    """
    The test we kept deferring: prove that a hand-written, genuinely
    dangerous query is blocked by run_query() itself -- not just by
    validate_query_safety() in isolation, but through the real code
    path that would be used in production.
    """
    print("\n--- run_query security guardrail (end-to-end) ---")
    results = []

    dangerous_queries = [
        "DELETE FROM realtime_stop_updates WHERE departure_delay > 1000",
        "DROP TABLE trips",
        "UPDATE realtime_stop_updates SET departure_delay = 0",
    ]

    for query in dangerous_queries:
        try:
            run_query(query)
            results.append(check(f"blocked: {query[:40]}...", False))
        except ValueError:
            results.append(check(f"blocked: {query[:40]}...", True))
        except Exception as e:
            # Any OTHER exception means it reached the database layer --
            # i.e. the guardrail did NOT catch it before execution.
            results.append(check(
                f"blocked BEFORE reaching the database: {query[:40]}... "
                f"(got unexpected {type(e).__name__} instead)",
                False
            ))

    return all(results)


def main():
    results = {
        "clean_sql_response": test_clean_sql_response(),
        "validate_query_safety": test_validate_query_safety(),
        "detect_delay_unit": test_detect_delay_unit(),
        "run_query security (end-to-end)": test_security_guardrail_end_to_end(),
    }

    print("\n=== SUMMARY ===")
    for name, passed in results.items():
        print(f"  {'PASS' if passed else 'FAIL'} - {name}")

    if all(results.values()):
        print("\nAll test groups passed.")
    else:
        print("\nSome tests failed -- see details above.")


if __name__ == "__main__":
    main()