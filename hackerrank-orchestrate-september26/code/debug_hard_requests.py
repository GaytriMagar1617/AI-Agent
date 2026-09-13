import pandas as pd

from data_loader import FinancialDataLoader
from message_extractor import MessageExtractor
from forecast_engine import ForecastEngine
from cashflow_simulator import CashFlowSimulator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine


loader = FinancialDataLoader()

request_ids = [
    "request_28",
    "request_31",
    "request_32",
    "request_33",
    "request_35"
]


for request_id in request_ids:

    print("\n" + "=" * 90)
    print(f"REQUEST: {request_id}")
    print("=" * 90)

    # ---------------------------------------------------------
    # CONTEXT
    # ---------------------------------------------------------

    context = loader.build_request_context(request_id)

    request = context["request"]
    profile = context["user_profile"]

    requested_amount = float(
        request["requested_amount"]
    )

    request_date = pd.Timestamp(
        request["request_date"]
    ).normalize()

    desired_date = pd.Timestamp(
        request["desired_completion_date"]
    ).normalize()

    print("Requested amount :", requested_amount)
    print("Request date     :", request_date.date())
    print("Desired date     :", desired_date.date())

    print(
        "Current balance  :",
        profile["current_available_balance"]
    )

    print(
        "Minimum balance  :",
        profile["minimum_balance_to_keep"]
    )

    print(
        "Accepted methods:",
        profile.get(
            "payment_methods_user_will_consider"
        )
    )

    # ---------------------------------------------------------
    # EVENTS
    # ---------------------------------------------------------

    events = pd.DataFrame(
        context.get(
            "financial_events",
            []
        )
    )

    # ---------------------------------------------------------
    # MESSAGES
    # ---------------------------------------------------------

    extractor = MessageExtractor(
        context.get(
            "messages",
            []
        )
    )

    message_evidence = extractor.extract_all()

    # ---------------------------------------------------------
    # FORECAST
    # ---------------------------------------------------------

    forecast_engine = ForecastEngine(
        context
    )

    forecast = forecast_engine.generate_forecast(
        end_date=desired_date.date()
    )

    # ---------------------------------------------------------
    # SIMULATOR
    # ---------------------------------------------------------

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

        request_date=request_date,

        home_currency=profile[
            "home_currency"
        ],

        financial_events=events,

        message_evidence=message_evidence,

        forecast=forecast
    )

    # ---------------------------------------------------------
    # PAYMENT PLANNER
    # ---------------------------------------------------------

    planner = PaymentPlanner(
        context=context,
        simulator=simulator
    )

    valid_options = (
        planner.get_valid_payment_options()
    )

    print(
        "\nValid payment options:",
        len(valid_options)
    )

    if not valid_options.empty:

        print(
            valid_options.to_string(
                index=False
            )
        )

    else:

        print("NO VALID OPTIONS")

    # ---------------------------------------------------------
    # EVALUATE OPTIONS
    # ---------------------------------------------------------

    evaluations = (
        simulator.evaluate_payment_options(
            payment_options=valid_options,
            end_date=desired_date
        )
    )

    print(
        "\nPAYMENT EVALUATIONS:"
    )

    if not evaluations:

        print("No evaluations.")

    else:

        for evaluation in evaluations:

            print("\n" + "-" * 70)

            print(
                "Option ID:",
                evaluation.get(
                    "payment_option_id"
                )
            )

            print(
                "Method:",
                evaluation.get(
                    "payment_method"
                )
            )

            print(
                "Safe:",
                evaluation.get(
                    "safe"
                )
            )

            print(
                "Reason:",
                evaluation.get(
                    "reason",
                    "No reason supplied"
                )
            )

            print(
                "Minimum balance seen:",
                evaluation.get(
                    "minimum_balance_seen"
                )
            )

            print(
                "Unsafe days:",
                evaluation.get(
                    "unsafe_days"
                )
            )

            print(
                "Financing fee:",
                evaluation.get(
                    "financing_fee",
                    0
                )
            )

            schedule = evaluation.get(
                "schedule",
                []
            )

            print("Schedule:")

            for payment in schedule:

                print(
                    " ",
                    payment["date"].strftime(
                        "%Y-%m-%d"
                    ),
                    "→",
                    payment["amount"]
                )

    # ---------------------------------------------------------
    # FINAL DECISION
    # ---------------------------------------------------------

    engine = DecisionEngine(
        context=context,
        simulator=simulator,
        payment_planner=planner
    )

    decision = engine.decide()

    print(
        "\nFINAL DECISION:"
    )

    for key, value in decision.items():

        print(
            f"{key}: {value}"
        )