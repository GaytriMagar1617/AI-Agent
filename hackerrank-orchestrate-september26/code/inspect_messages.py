import pandas as pd

from data_loader import FinancialDataLoader


loader = FinancialDataLoader()

context = loader.build_request_context("request_26")

messages = context["messages"]

print("\n" + "=" * 80)
print("MESSAGE STRUCTURE")
print("=" * 80)

if not messages:
    print("No messages found.")
    exit()

df = pd.DataFrame(messages)

print("\nColumns:")
print(df.columns.tolist())

print("\n" + "=" * 80)
print("ALL MESSAGES FOR USER")
print("=" * 80)

print(df.to_string(index=False))