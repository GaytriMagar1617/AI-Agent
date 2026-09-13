import pandas as pd

from data_loader import FinancialDataLoader
from message_extractor import MessageExtractor
from forecast_engine import ForecastEngine
from cashflow_simulator import CashFlowSimulator


# ================================================================
# CASH FLOW SIMULATOR TEST
# ================================================================

print("\n" + "=" * 70)
print("CASH FLOW SIMULATOR TEST")
print("=" * 70)


# ================================================================
# STEP 1: LOAD DATA
# ================================================================

loader = FinancialDataLoader()

request_id = "request_26"

print(f"\nTesting request: {request_id}")

context = loader.build_request_context(request_id)

request = context["request"]
profile = context["user_profile"]

financial_events = context["financial_events"]
messages = context["messages"]


# ================================================================
# STEP 2: CONVERT FINANCIAL EVENTS TO DATAFRAME
# ================================================================

if isinstance(financial_events, list):
    financial_events = pd.DataFrame(financial_events)

print("\nFinancial events type:", type(financial_events).__name__)

if isinstance(financial_events, pd.DataFrame):
    print("Financial events rows:", len(financial_events))


# ================================================================
# STEP 3: REQUEST INFORMATION
# ================================================================

print("\n" + "=" * 70)
print("REQUEST INFORMATION")
print("=" * 70)

print("Request ID       :", request_id)
print("User ID          :", request["user_id"])
print("Request Type     :", request["request_type"])
print("Requested Amount :", request["requested_amount"])
print("Request Date     :", request["request_date"])
print("Completion Date  :", request["desired_completion_date"])
print("Home Currency    :", profile["home_currency"])
print("Current Balance  :", profile["current_available_balance"])
print("Minimum Balance  :", profile["minimum_balance_to_keep"])


# ================================================================
# STEP 4: MESSAGE EVIDENCE
# ================================================================

print("\n" + "=" * 70)
print("MESSAGE EVIDENCE")
print("=" * 70)

message_extractor = MessageExtractor(messages)

message_evidence = message_extractor.extract_all()

print(
    "Financial messages found:",
    len(message_evidence)
)

for message in message_evidence:

    print(
        message.get("message_id"),
        "|",
        message.get("financial_type"),
        "|",
        message.get("amount"),
        "|",
        message.get("expected_date"),
        "|",
        message.get("confirmation")
    )


# ================================================================
# STEP 5: GENERATE FORECAST
# ================================================================

print("\n" + "=" * 70)
print("FORECAST")
print("=" * 70)

forecast_engine = ForecastEngine(context)

forecast = forecast_engine.generate_forecast(
    request["desired_completion_date"]
)


# ================================================================
# FORECAST MUST REMAIN A DATAFRAME
# ================================================================

print("\nForecast object type:")
print(type(forecast).__name__)


if isinstance(forecast, pd.DataFrame):

    forecast_transactions = forecast

elif isinstance(forecast, list):

    forecast_transactions = pd.DataFrame(
        forecast
    )

elif isinstance(forecast, dict):

    if "transactions" in forecast:

        transactions = forecast["transactions"]

        if isinstance(transactions, pd.DataFrame):

            forecast_transactions = transactions

        elif isinstance(transactions, list):

            forecast_transactions = pd.DataFrame(
                transactions
            )

        else:

            forecast_transactions = pd.DataFrame()

    else:

        forecast_transactions = pd.DataFrame(
            forecast
        )

else:

    forecast_transactions = pd.DataFrame()


# ================================================================
# DISPLAY FORECAST
# ================================================================

print(
    "\nForecast transactions:",
    len(forecast_transactions)
)


if not forecast_transactions.empty:

    for _, item in forecast_transactions.head(10).iterrows():

        print(
            item.get("date"),
            "|",
            item.get("category"),
            "|",
            item.get("amount"),
            "|",
            item.get("direction")
        )


# ================================================================
# VERIFY FORECAST
# ================================================================

if forecast_transactions.empty:

    print("\n" + "=" * 70)
    print("FORECAST CONVERSION FAILED")
    print("=" * 70)

    print(
        "\nForecast returned:"
    )

    print(
        repr(forecast)
    )

    raise SystemExit


# ================================================================
# STEP 6: CREATE CASH FLOW SIMULATOR
# ================================================================

print("\n" + "=" * 70)
print("CREATING CASH FLOW SIMULATOR")
print("=" * 70)


simulator = CashFlowSimulator(

    current_balance=profile[
        "current_available_balance"
    ],

    minimum_balance=profile[
        "minimum_balance_to_keep"
    ],

    request_date=request[
        "request_date"
    ],

    home_currency=profile[
        "home_currency"
    ],

    financial_events=financial_events,

    message_evidence=message_evidence,

    forecast=forecast_transactions
)


print(
    "CashFlowSimulator created successfully."
)


# ================================================================
# COMMON VARIABLES
# ================================================================

requested_amount = float(
    request["requested_amount"]
)

payment_date = request[
    "request_date"
]

end_date = request[
    "desired_completion_date"
]


# ================================================================
# TEST 1 - FULL PAYMENT
# ================================================================

print("\n" + "=" * 70)
print("TEST 1 - FULL PAYMENT")
print("=" * 70)


result = simulator.check_full_payment(

    requested_amount,

    payment_date,

    end_date
)


print(
    "Requested amount :",
    requested_amount
)

print(
    "Payment date     :",
    payment_date
)

print(
    "End date         :",
    end_date
)

print(
    "\nSafe             :",
    result.get("safe")
)

print(
    "Minimum balance  :",
    result.get("min_balance")
)

print(
    "Unsafe days      :",
    result.get("unsafe_days")
)


# ================================================================
# TEST 2 - MAXIMUM SAFE AMOUNT
# ================================================================

print("\n" + "=" * 70)
print("TEST 2 - MAXIMUM SAFE AMOUNT")
print("=" * 70)


safe_amount = simulator.find_safe_amount(

    payment_date,

    end_date,

    requested_amount
)


print(
    "Requested amount    :",
    requested_amount
)

print(
    "Maximum safe amount :",
    safe_amount
)


# ================================================================
# TEST 3 - EARLIEST SAFE DATE
# ================================================================

print("\n" + "=" * 70)
print("TEST 3 - EARLIEST SAFE DATE")
print("=" * 70)


earliest_date = simulator.find_earliest_safe_date(

    requested_amount,

    payment_date,

    end_date
)


print(
    "Requested amount    :",
    requested_amount
)

print(
    "Start date          :",
    payment_date
)

print(
    "End date            :",
    end_date
)

print(
    "Earliest safe date  :",
    earliest_date
)


# ================================================================
# TEST 4 - TWO PAYMENT PLAN
# ================================================================

print("\n" + "=" * 70)
print("TEST 4 - TWO PAYMENT PLAN")
print("=" * 70)


first_payment = requested_amount / 2

second_payment = (
    requested_amount -
    first_payment
)


payments = [

    {
        "date": payment_date,
        "amount": first_payment
    },

    {
        "date": end_date,
        "amount": second_payment
    }

]


plan_result = simulator.check_payment_plan(

    payments,

    end_date
)


print("Payment 1:")

print(
    "  Date   :",
    payments[0]["date"]
)

print(
    "  Amount :",
    payments[0]["amount"]
)


print("\nPayment 2:")

print(
    "  Date   :",
    payments[1]["date"]
)

print(
    "  Amount :",
    payments[1]["amount"]
)


print(
    "\nPlan safe       :",
    plan_result.get("safe")
)

print(
    "Minimum balance :",
    plan_result.get("min_balance")
)

print(
    "Unsafe days     :",
    plan_result.get("unsafe_days")
)


# ================================================================
# TEST 5 - BASELINE CASH FLOW
# ================================================================

print("\n" + "=" * 70)
print("TEST 5 - BASELINE CASH FLOW")
print("=" * 70)


simulation = simulator.simulate(
    end_date
)


print(
    "Simulation type:",
    type(simulation).__name__
)

print(
    "Simulation days:",
    len(simulation)
)


# ================================================================
# SIMULATION IS A PANDAS DATAFRAME
# ================================================================

if isinstance(simulation, pd.DataFrame):

    if not simulation.empty:

        print(
            "\nSimulation columns:"
        )

        print(
            list(simulation.columns)
        )


        # --------------------------------------------------------
        # Find balance column
        # --------------------------------------------------------

        if "ending_balance" in simulation.columns:

            minimum_balance_seen = simulation["ending_balance"].min()
            maximum_balance_seen = simulation["ending_balance"].max()
            final_balance = simulation["ending_balance"].iloc[-1]


            print(
                "\nMinimum balance seen:",
                minimum_balance_seen
            )

            print(
                "Maximum balance seen:",
                maximum_balance_seen
            )

            print(
                "Final balance       :",
                final_balance
            )


            # ----------------------------------------------------
            # Check minimum balance requirement
            # ----------------------------------------------------

            minimum_required = float(
                profile["minimum_balance_to_keep"]
            )


            print(
                "Required minimum    :",
                minimum_required
            )


            if minimum_balance_seen >= minimum_required:

                print(
                    "Minimum balance check: PASSED"
                )

            else:

                print(
                    "Minimum balance check: FAILED"
                )


        else:

            print(
                "\nWARNING: 'balance' column "
                "was not found."
            )

            print(
                simulation.head()
            )

    else:

        print(
            "\nWARNING: Simulation DataFrame is empty."
        )


else:

    print(
        "\nWARNING: Simulation is not a DataFrame."
    )

    print(
        repr(simulation)
    )

# ================================================================
# FINAL TEST SUMMARY
# ================================================================

print("\n" + "=" * 70)
print("FINAL TEST SUMMARY")
print("=" * 70)


print(
    "Full payment safe     :",
    result.get("safe")
)

print(
    "Maximum safe amount   :",
    safe_amount
)

print(
    "Earliest safe date    :",
    earliest_date
)

print(
    "Two-payment plan safe :",
    plan_result.get("safe")
)


print("\n" + "=" * 70)
print("CASH FLOW SIMULATOR TEST COMPLETE")
print("=" * 70)