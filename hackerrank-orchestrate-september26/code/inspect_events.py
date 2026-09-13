import pandas as pd
from data_loader import FinancialDataLoader

loader = FinancialDataLoader()

context = loader.build_request_context("request_26")

events = context["financial_events"]

df = pd.DataFrame(events)

print("\n" + "=" * 80)
print("USER_26 EVENT STRUCTURE")
print("=" * 80)

print("\nColumns:")
print(df.columns.tolist())

print("\n" + "=" * 80)
print("EVENT TYPES")
print("=" * 80)
print(df["event_type"].value_counts(dropna=False))

print("\n" + "=" * 80)
print("STATUSES")
print("=" * 80)

if "status" in df.columns:
    print(df["status"].value_counts(dropna=False))

print("\n" + "=" * 80)
print("DIRECTIONS")
print("=" * 80)

if "direction" in df.columns:
    print(df["direction"].value_counts(dropna=False))

print("\n" + "=" * 80)
print("CATEGORIES")
print("=" * 80)

if "category" in df.columns:
    print(df["category"].value_counts(dropna=False))

print("\n" + "=" * 80)
print("FUTURE EVENTS AFTER 2025-08-03")
print("=" * 80)

df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")

future = df[df["event_date"] > pd.Timestamp("2025-08-03")]

print(
    future[
        [
            c for c in [
                "event_id",
                "event_date",
                "event_type",
                "category",
                "amount",
                "currency",
                "direction",
                "status",
                "flexibility",
                "minimum_allowed_amount",
                "linked_event_id"
            ]
            if c in future.columns
        ]
    ].to_string(index=False)
)