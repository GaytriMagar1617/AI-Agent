"""
BUY OR WAIT?
FULL PIPELINE TEST

Stages:
1. Load dataset
2. Build request context
3. Extract message evidence
4. Generate forecast
5. Create cash-flow simulator
6. Build valid payment options
7. Evaluate payment options
8. Check full payment
9. Find earliest safe date
10. Find maximum safe amount
11. Produce preliminary decision

This file is for testing the financial pipeline.
"""

import pandas as pd

from data_loader import FinancialDataLoader
from message_extractor import MessageExtractor
from forecast_engine import ForecastEngine
from cashflow_simulator import CashFlowSimulator
from payment_planner import PaymentPlanner


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_value(obj, key, default=None):
    """Safely get a value from dictionary/object."""

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def dataframe_to_records(data):
    """
    Convert DataFrame/list/dict into a list of dictionaries.
    """

    if data is None:
        return []

    if isinstance(data, pd.DataFrame):
        return data.to_dict(orient="records")

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return [data]

    return []


def print_line():
    print("-" * 75)


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():

    print("=" * 75)
    print("BUY OR WAIT? - FULL PIPELINE TEST")
    print("=" * 75)

    # ========================================================
    # STEP 1
    # ========================================================

    print("\n[1] LOADING DATASET...")

    loader = FinancialDataLoader()

    print("\nDataset loaded successfully.")

    # ========================================================
    # REQUEST TO TEST
    # ========================================================

    request_id = "request_26"

    # ========================================================
    # STEP 2 - BUILD CONTEXT
    # ========================================================

    print(
        f"\n[2] BUILDING CONTEXT FOR {request_id}..."
    )

    context = loader.build_request_context(
        request_id
    )

    if not context:
        raise RuntimeError(
            f"Could not build context for {request_id}"
        )

    request = context["request"]

    profile = context["user_profile"]

    # Convert dates to pandas Timestamp
    request_date = pd.Timestamp(
        request["request_date"]
    ).normalize()

    desired_completion_date = pd.Timestamp(
        request["desired_completion_date"]
    ).normalize()

    requested_amount = float(
        request["requested_amount"]
    )

    print(
        f"User: {request['user_id']}"
    )

    print(
        f"Request type: {request['request_type']}"
    )

    print(
        f"Requested amount: {requested_amount}"
    )

    print(
        f"Request date: {request_date.date()}"
    )

    print(
        f"Desired completion date: "
        f"{desired_completion_date.date()}"
    )

    # ========================================================
    # STEP 3 - MESSAGE EXTRACTION
    # ========================================================

    print(
        "\n[3] EXTRACTING MESSAGE EVIDENCE..."
    )

    messages = context.get(
        "messages",
        []
    )

    print(
        f"Messages available for request: "
        f"{len(messages)}"
    )

    extractor = MessageExtractor(
        messages
    )

    # Actual method in your MessageExtractor
    message_evidence = extractor.extract_all()

    print(
        f"Financial messages found: "
        f"{len(message_evidence)}"
    )

    for item in message_evidence:

        print(
            f"  {item.get('message_id')} | "
            f"{item.get('financial_type')} | "
            f"{item.get('amount')} | "
            f"{item.get('expected_date')} | "
            f"{item.get('confirmation')}"
        )

    # ========================================================
    # STEP 4 - FORECAST
    # ========================================================

    print(
        "\n[4] GENERATING FORECAST..."
    )

    forecast_engine = ForecastEngine(
        context
    )

    # IMPORTANT:
    # ForecastEngine.generate_forecast()
    # expects datetime.date

    forecast = forecast_engine.generate_forecast(
        desired_completion_date.date()
    )

    print(
        "Forecast generated successfully."
    )

    if isinstance(forecast, dict):

        transactions = forecast.get(
            "transactions",
            []
        )

        print(
            f"Forecast transactions: "
            f"{len(transactions)}"
        )

        if "total_forecast_expenses" in forecast:

            print(
                "Forecast expenses:",
                forecast[
                    "total_forecast_expenses"
                ]
            )

        if "total_forecast_income" in forecast:

            print(
                "Forecast income:",
                forecast[
                    "total_forecast_income"
                ]
            )

    elif isinstance(forecast, list):

        print(
            f"Forecast transactions: "
            f"{len(forecast)}"
        )

    else:

        print(
            "Forecast generated."
        )

    # ========================================================
    # STEP 5 - CASH FLOW SIMULATOR
    # ========================================================

    print(
        "\n[5] RUNNING CASH FLOW SIMULATION..."
    )

    financial_events = context.get(
        "financial_events",
        []
    )

    if isinstance(
        financial_events,
        pd.DataFrame
    ):

        events_df = financial_events.copy()

    else:

        events_df = pd.DataFrame(
            financial_events
        )

    simulator = CashFlowSimulator(

        current_balance=profile[
            "current_available_balance"
        ],

        minimum_balance=profile[
            "minimum_balance_to_keep"
        ],

        request_date=request_date,

        home_currency=profile[
            "home_currency"
        ],

        financial_events=events_df,

        message_evidence=message_evidence,

        forecast=forecast
    )

    print(
        "Cash flow simulator created successfully."
    )

    # ========================================================
    # STEP 6 - PAYMENT PLANNER
    # ========================================================

    print(
        "\n[6] BUILDING PAYMENT PLAN..."
    )

    payment_planner = PaymentPlanner(
        context,
        simulator=simulator
    )

    # Your PaymentPlanner returns a DataFrame
    valid_options_data = (
        payment_planner
        .get_valid_payment_options()
    )

    # Convert DataFrame -> list of dictionaries
    valid_options = dataframe_to_records(
        valid_options_data
    )

    print(
        f"Valid payment options: "
        f"{len(valid_options)}"
    )

    if len(valid_options) == 0:

        print(
            "No valid payment options found."
        )

    else:

        for option in valid_options:

            print(
                f"  "
                f"{option.get('payment_option_id')} | "
                f"{option.get('payment_method')} | "
                f"Amount: "
                f"{option.get('payment_amount')} | "
                f"Payments: "
                f"{option.get('number_of_payments')} | "
                f"First date: "
                f"{option.get('first_payment_date')}"
            )

    # ========================================================
    # STEP 7 - EVALUATE PAYMENT OPTIONS
    # ========================================================

    print(
        "\n[7] EVALUATING PAYMENT OPTIONS..."
    )

    option_results_raw = []

    if len(valid_options) > 0:

        option_results_raw = (
            simulator.evaluate_payment_options(

                payment_options=valid_options,

                end_date=desired_completion_date
            )
        )

    # Make result iterable safely
    if isinstance(
        option_results_raw,
        pd.DataFrame
    ):

        option_results = (
            option_results_raw
            .to_dict(
                orient="records"
            )
        )

    elif isinstance(
        option_results_raw,
        list
    ):

        option_results = (
            option_results_raw
        )

    else:

        option_results = []

    print(
        f"Payment options evaluated: "
        f"{len(option_results)}"
    )

    for item in option_results:

        # Simulator normally returns:
        # {"option": ..., "result": ...}

        if isinstance(item, dict):

            option = item.get(
                "option"
            )

            result = item.get(
                "result"
            )

        else:

            option = None
            result = item

        if option is None:
            continue

        print_line()

        print(
            "Option:",
            option.get(
                "payment_option_id"
            )
        )

        print(
            "Method:",
            option.get(
                "payment_method"
            )
        )

        print(
            "Payment amount:",
            option.get(
                "payment_amount"
            )
        )

        print(
            "Number of payments:",
            option.get(
                "number_of_payments"
            )
        )

        print(
            "Safe:",
            get_value(
                result,
                "safe",
                False
            )
        )

        minimum_balance_seen = (
            get_value(
                result,
                "minimum_balance_seen",
                None
            )
        )

        if minimum_balance_seen is not None:

            print(
                "Minimum balance seen:",
                minimum_balance_seen
            )

        unsafe_days = get_value(
            result,
            "unsafe_days",
            None
        )

        if unsafe_days is not None:

            print(
                "Unsafe days:",
                unsafe_days
            )

    # ========================================================
    # STEP 8 - FULL PAYMENT TODAY
    # ========================================================

    print(
        "\n[8] CHECKING FULL PAYMENT TODAY..."
    )

    full_payment_result = None

    try:

        full_payment_result = (
            simulator.check_full_payment(

                requested_amount=requested_amount,

                payment_date=request_date,

                end_date=desired_completion_date
            )
        )

        full_payment_safe = get_value(
            full_payment_result,
            "safe",
            False
        )

        minimum_balance_seen = get_value(
            full_payment_result,
            "minimum_balance_seen",
            None
        )

        unsafe_days = get_value(
            full_payment_result,
            "unsafe_days",
            None
        )

        print(
            "Full payment safe:",
            full_payment_safe
        )

        if minimum_balance_seen is not None:

            print(
                "Minimum balance seen:",
                minimum_balance_seen
            )

        if unsafe_days is not None:

            print(
                "Unsafe days:",
                unsafe_days
            )

    except Exception as e:

        print(
            "Full payment check failed:"
        )

        print(
            str(e)
        )

    # ========================================================
    # STEP 9 - EARLIEST SAFE DATE
    # ========================================================

    print(
        "\n[9] FINDING EARLIEST SAFE DATE..."
    )

    earliest_safe_date = None

    try:

        earliest_safe_date = (
            simulator.find_earliest_safe_date(

                requested_amount=requested_amount,

                start_date=request_date,

                end_date=desired_completion_date
            )
        )

        print(
            "Earliest safe date:",
            earliest_safe_date
        )

    except Exception as e:

        print(
            "Earliest safe date check failed:"
        )

        print(
            str(e)
        )

    # ========================================================
    # STEP 10 - MAXIMUM SAFE AMOUNT
    # ========================================================

    print(
        "\n[10] CALCULATING MAXIMUM SAFE PAYMENT..."
    )

    maximum_safe_amount = 0

    try:

        maximum_safe_amount = (
            simulator.find_safe_amount(

                payment_date=request_date,

                end_date=desired_completion_date,

                requested_amount=requested_amount
            )
        )

        print(
            "Requested amount:",
            requested_amount
        )

        print(
            "Maximum safe amount:",
            maximum_safe_amount
        )

    except Exception as e:

        print(
            "Maximum safe amount check failed:"
        )

        print(
            str(e)
        )

    # ========================================================
    # STEP 11 - PRELIMINARY DECISION
    # ========================================================

    print(
        "\n[11] GENERATING PRELIMINARY DECISION..."
    )

    full_payment_safe = False

    if full_payment_result is not None:

        full_payment_safe = get_value(
            full_payment_result,
            "safe",
            False
        )

    # Determine preliminary status
    if (
        full_payment_safe
        and maximum_safe_amount >= requested_amount
    ):

        affordability_status = (
            "affordable_now"
        )

        recommended_payment_method = (
            "full_payment"
        )

        payment_plan = (
            f"Pay full amount of "
            f"{requested_amount:.2f} "
            f"on {request_date.date()}"
        )

        decision = "BUY / PAY NOW"

    elif (
        maximum_safe_amount > 0
        and maximum_safe_amount < requested_amount
    ):

        affordability_status = (
            "affordable_with_plan"
        )

        recommended_payment_method = (
            "installments"
        )

        payment_plan = (
            "Use a valid installment option "
            "within the user's constraints."
        )

        decision = "PAY WITH PLAN"

    elif earliest_safe_date is not None:

        affordability_status = (
            "affordable_later"
        )

        recommended_payment_method = (
            "wait"
        )

        payment_plan = (
            f"Wait until "
            f"{earliest_safe_date}"
        )

        decision = "WAIT"

    else:

        affordability_status = (
            "not_affordable"
        )

        recommended_payment_method = (
            "not_recommended"
        )

        payment_plan = (
            "Do not make the payment "
            "under the current financial conditions."
        )

        decision = "DO NOT PAY"

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    print("\n")
    print("=" * 75)
    print("FINAL PRELIMINARY DECISION")
    print("=" * 75)

    print(
        f"Request ID: "
        f"{request_id}"
    )

    print(
        f"Requested amount: "
        f"{requested_amount:.2f}"
    )

    print(
        f"Affordability status: "
        f"{affordability_status}"
    )

    print(
        f"Recommended payment method: "
        f"{recommended_payment_method}"
    )

    print(
        f"Payment plan: "
        f"{payment_plan}"
    )

    print(
        f"Earliest safe date: "
        f"{earliest_safe_date}"
    )

    print(
        f"Maximum safe amount today: "
        f"{maximum_safe_amount}"
    )

    print(
        f"Decision: "
        f"{decision}"
    )

    print("=" * 75)

    # ========================================================
    # COMPLETED
    # ========================================================

    print(
        "\nPIPELINE TEST COMPLETED SUCCESSFULLY."
    )

    print(
        "All core financial stages executed."
    )

    print("=" * 75)


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()