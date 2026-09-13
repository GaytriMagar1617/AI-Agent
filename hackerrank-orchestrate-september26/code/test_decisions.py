import pandas as pd

from data_loader import FinancialDataLoader
from message_extractor import MessageExtractor
from forecast_engine import ForecastEngine
from cashflow_simulator import CashFlowSimulator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine


# ---------------------------------------------------------
# TEST MULTIPLE REQUESTS
# ---------------------------------------------------------

loader = FinancialDataLoader()


# ---------------------------------------------------------
# GET ACTUAL REQUEST IDs FROM DATASET
# ---------------------------------------------------------

actual_request_ids = (
    loader.requests["request_id"]
    .astype(str)
    .tolist()
)


# Make sure request_26 is tested
# Test requests 26 to 35 specifically
test_requests = [
    f"request_{i}"
    for i in range(26, 36)
    if f"request_{i}" in actual_request_ids
]

print("\n" + "=" * 100)
print("DECISION ENGINE - MULTI REQUEST TEST")
print("=" * 100)

print("\nActual test request IDs:")
print(test_requests)


# ---------------------------------------------------------
# TEST EACH REQUEST
# ---------------------------------------------------------

for request_id in test_requests:

    print(f"\n{'-' * 100}")
    print(f"Testing: {request_id}")
    print(f"{'-' * 100}")

    try:

        # =================================================
        # 1. BUILD CONTEXT
        # =================================================

        context = loader.build_request_context(
            request_id
        )


        # =================================================
        # 2. EXTRACT MESSAGE EVIDENCE
        # =================================================

        message_extractor = MessageExtractor(
            context["messages"]
        )

        message_evidence = (
            message_extractor.extract_all()
        )


        # =================================================
        # 3. CONVERT FINANCIAL EVENTS TO DATAFRAME
        # =================================================

        financial_events = pd.DataFrame(
            context.get(
                "financial_events",
                []
            )
        )


        # =================================================
        # 4. GENERATE FORECAST
        # =================================================

        forecast_engine = ForecastEngine(
            context
        )

        forecast = forecast_engine.generate_forecast(
            context["request"][
                "desired_completion_date"
            ]
        )


        # =================================================
        # 5. CREATE CASH FLOW SIMULATOR
        # =================================================

        profile = context["user_profile"]

        simulator = CashFlowSimulator(

            current_balance=float(
                profile[
                    "current_available_balance"
                ]
            ),

            minimum_balance=float(
                profile[
                    "minimum_balance_to_keep"
                ]
            ),

            request_date=context[
                "request"
            ][
                "request_date"
            ],

            home_currency=profile[
                "home_currency"
            ],

            financial_events=financial_events,

            message_evidence=message_evidence,

            forecast=forecast,
        )


        # =================================================
        # 6. PAYMENT PLANNER
        # =================================================

        planner = PaymentPlanner(
            context,
            simulator=simulator
        )


        # =================================================
        # 7. DECISION ENGINE
        # =================================================

        decision_engine = DecisionEngine(

            context=context,

            simulator=simulator,

            payment_planner=planner

        )


        # =================================================
        # 8. GET FINAL DECISION
        # =================================================

        decision = decision_engine.decide()


        # =================================================
        # 9. DISPLAY RESULT
        # =================================================

        print(
            f"Requested Amount : "
            f"{decision['amount_safe_to_pay']}"
        )

        print(
            f"Status           : "
            f"{decision['affordability_status']}"
        )

        print(
            f"Payment Method   : "
            f"{decision['recommended_payment_method']}"
        )

        print(
            f"Payment Plan     : "
            f"{decision['payment_plan']}"
        )

        print(
            f"Earliest Date    : "
            f"{decision['earliest_date_for_full_payment']}"
        )

        print(
            f"Spending Changes : "
            f"{decision['spending_changes_needed']}"
        )

        print(
            f"Explanation      : "
            f"{decision['decision_explanation']}"
        )


    except Exception as e:
     import traceback
    print(f"ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n" + "=" * 100)
print("MULTI REQUEST TEST COMPLETE")
print("=" * 100)