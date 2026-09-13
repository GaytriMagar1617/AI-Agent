import pandas as pd
from datetime import timedelta


class CashFlowSimulator:

    def __init__(
        self,
        current_balance,
        minimum_balance,
        request_date,
        home_currency,
        financial_events=None,
        message_evidence=None,
        forecast=None
    ):
        self.current_balance = float(current_balance)
        self.minimum_balance = float(minimum_balance)
        self.request_date = pd.Timestamp(request_date).normalize()
        self.home_currency = str(home_currency).strip().upper()

        self.financial_events = (
            financial_events
            if financial_events is not None
            else pd.DataFrame()
        )

        self.message_evidence = (
            message_evidence
            if message_evidence is not None
            else []
        )

        self.forecast = (
            forecast
            if forecast is not None
            else pd.DataFrame()
        )

    # =========================================================
    # UTILITY FUNCTIONS
    # =========================================================

    @staticmethod
    def _safe_float(value, default=None):

        if value is None:
            return default

        try:
            if pd.isna(value):
                return default
        except Exception:
            pass

        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _normalize_date(value):

        if value is None:
            return None

        try:
            if pd.isna(value):
                return None
        except Exception:
            pass

        try:
            return pd.Timestamp(value).normalize()
        except Exception:
            return None

    @staticmethod
    def _normalize_text(value):

        if value is None:
            return ""

        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass

        return str(value).strip().lower()

    # =========================================================
    # 1. STRUCTURED FUTURE CASH FLOWS
    # =========================================================

    def get_structured_cashflows(self):

        flows = []

        if self.financial_events.empty:
            return flows

        for _, event in self.financial_events.iterrows():

            # -------------------------------------------------
            # Status
            # -------------------------------------------------

            status = self._normalize_text(
                event.get("status", "")
            )

            # Cancelled / failed events have no cash impact
            if status in [
                "cancelled",
                "canceled",
                "failed"
            ]:
                continue

            # -------------------------------------------------
            # Settlement date
            # -------------------------------------------------

            settlement_date = self._normalize_date(
                event.get("settlement_date")
            )

            event_date = self._normalize_date(
                event.get("event_date")
            )

            # Prefer settlement date when available.
            flow_date = settlement_date or event_date

            if flow_date is None:
                continue

            # Only future cash flows
            if flow_date <= self.request_date:
                continue

            # -------------------------------------------------
            # Currency
            # -------------------------------------------------

            currency = self._normalize_text(
                event.get("currency", "")
            ).upper()

            if not currency:
                continue

            if currency != self.home_currency:
                continue

            # -------------------------------------------------
            # Amount
            # -------------------------------------------------

            amount = self._safe_float(
                event.get("amount")
            )

            if amount is None or amount <= 0:
                continue

            # -------------------------------------------------
            # Direction
            # -------------------------------------------------

            direction = self._normalize_text(
                event.get("direction", "")
            )

            category = event.get(
                "category",
                ""
            )

            # -------------------------------------------------
            # CREDIT
            # -------------------------------------------------

            if direction == "credit":

                # Important:
                # Pending credits must NOT be counted.
                #
                # Only settled/scheduled/confirmed credits
                # are considered usable future income.
                if status in [
                    "settled",
                    "scheduled",
                    "confirmed"
                ]:

                    flows.append({
                        "date": flow_date,
                        "amount": amount,
                        "type": "income",
                        "source": "financial_event",
                        "category": category,
                        "event_id": event.get("event_id")
                    })

            # -------------------------------------------------
            # DEBIT
            # -------------------------------------------------

            elif direction == "debit":

                # Future scheduled/pending/confirmed debits
                # should be reserved.
                if status in [
                    "settled",
                    "scheduled",
                    "pending",
                    "confirmed"
                ]:

                    flows.append({
                        "date": flow_date,
                        "amount": amount,
                        "type": "expense",
                        "source": "financial_event",
                        "category": category,
                        "event_id": event.get("event_id")
                    })

        return flows

    # =========================================================
    # 2. MESSAGE-BASED CASH FLOWS
    # =========================================================

    def get_message_cashflows(self):

        flows = []

        for evidence in self.message_evidence:

            if not isinstance(evidence, dict):
                continue

            # -------------------------------------------------
            # Confirmation
            # -------------------------------------------------

            confirmation = self._normalize_text(
                evidence.get(
                    "confirmation",
                    ""
                )
            )

            # Only confirmed information can affect
            # available future cash.
            if confirmation != "confirmed":
                continue

            # -------------------------------------------------
            # Financial type
            # -------------------------------------------------

            financial_type = self._normalize_text(
                evidence.get(
                    "financial_type",
                    ""
                )
            )

            if financial_type != "income":
                continue

            # -------------------------------------------------
            # Amount
            # -------------------------------------------------

            amount = self._safe_float(
                evidence.get("amount")
            )

            if amount is None or amount <= 0:
                continue

            # -------------------------------------------------
            # Expected date
            # -------------------------------------------------

            expected_date = self._normalize_date(
                evidence.get("expected_date")
            )

            if expected_date is None:
                continue

            if expected_date <= self.request_date:
                continue

            # -------------------------------------------------
            # Currency
            # -------------------------------------------------

            currency = self._normalize_text(
                evidence.get("currency", "")
            ).upper()

            if currency != self.home_currency:
                continue

            # -------------------------------------------------
            # Add confirmed income
            # -------------------------------------------------

            flows.append({
                "date": expected_date,
                "amount": amount,
                "type": "income",
                "source": "message",
                "category": "message_income",
                "message_id": evidence.get("message_id")
            })

        return flows

    # =========================================================
    # 3. FORECAST CASH FLOWS
    # =========================================================

    def get_forecast_cashflows(self):

        flows = []

        if self.forecast.empty:
            return flows

        for _, row in self.forecast.iterrows():

            # -------------------------------------------------
            # Date
            # -------------------------------------------------

            date = self._normalize_date(
                row.get("date")
            )

            if date is None:
                continue

            if date <= self.request_date:
                continue

            # -------------------------------------------------
            # Amount
            # -------------------------------------------------

            amount = self._safe_float(
                row.get("amount")
            )

            if amount is None or amount <= 0:
                continue

            # -------------------------------------------------
            # Direction
            # -------------------------------------------------

            direction = self._normalize_text(
                row.get(
                    "direction",
                    "debit"
                )
            )

            category = row.get(
                "category",
                ""
            )

            # -------------------------------------------------
            # Currency
            # -------------------------------------------------

            currency = row.get(
                "currency",
                self.home_currency
            )

            currency = self._normalize_text(
                currency
            ).upper()

            if currency != self.home_currency:
                continue

            # -------------------------------------------------
            # Expense
            # -------------------------------------------------

            if direction == "debit":

                flows.append({
                    "date": date,
                    "amount": amount,
                    "type": "expense",
                    "source": "forecast",
                    "category": category
                })

            # -------------------------------------------------
            # Income
            # -------------------------------------------------

            elif direction == "credit":

                flows.append({
                    "date": date,
                    "amount": amount,
                    "type": "income",
                    "source": "forecast",
                    "category": category
                })

        return flows

    # =========================================================
    # 4. REMOVE DUPLICATE CASH FLOWS
    # =========================================================

    def remove_duplicate_cashflows(self, flows):

        if not flows:
            return []

        unique_flows = []

        seen = set()

        for flow in flows:

            date = self._normalize_date(
                flow.get("date")
            )

            amount = self._safe_float(
                flow.get("amount"),
                0.0
            )

            flow_type = self._normalize_text(
                flow.get("type")
            )

            category = self._normalize_text(
                flow.get("category")
            )

            source = self._normalize_text(
                flow.get("source")
            )

            # -------------------------------------------------
            # Prefer event/message identity when available
            # -------------------------------------------------

            event_id = flow.get("event_id")
            message_id = flow.get("message_id")

            if event_id is not None and not pd.isna(event_id):

                key = (
                    "event",
                    str(event_id)
                )

            elif message_id is not None and not pd.isna(message_id):

                key = (
                    "message",
                    str(message_id)
                )

            else:

                key = (
                    str(date),
                    round(amount, 2),
                    flow_type,
                    category,
                    source
                )

            if key not in seen:

                seen.add(key)
                unique_flows.append(flow)

        return unique_flows

    # =========================================================
    # 5. COMBINE ALL CASH FLOWS
    # =========================================================

    def get_all_cashflows(self):

        flows = []

        # Structured financial events
        flows.extend(
            self.get_structured_cashflows()
        )

        # Confirmed message evidence
        flows.extend(
            self.get_message_cashflows()
        )

        # Forecasted cash flows
        flows.extend(
            self.get_forecast_cashflows()
        )

        if not flows:
            return []

        # Remove duplicates
        flows = self.remove_duplicate_cashflows(
            flows
        )

        # Sort chronologically
        flows.sort(
            key=lambda x: x["date"]
        )

        return flows

    # =========================================================
    # 6. CREATE PAYMENT SCHEDULE FROM PAYMENT OPTION
    # =========================================================

    def create_payment_schedule(
        self,
        payment_option
    ):
        """
        Convert one payment option from payment_options.csv
        into the exact payment schedule that the simulator
        must evaluate.

        Expected columns:

        payment_option_id
        request_id
        payment_method
        payment_amount
        number_of_payments
        first_payment_date
        payment_frequency_days
        financing_fee
        total_payable_amount
        """

        if payment_option is None:
            return []

        # -----------------------------------------------------
        # Number of payments
        # -----------------------------------------------------

        number_of_payments = self._safe_float(
            payment_option.get(
                "number_of_payments"
            )
        )

        if number_of_payments is None:
            return []

        number_of_payments = int(
            number_of_payments
        )

        if number_of_payments <= 0:
            return []

        # -----------------------------------------------------
        # Payment amount
        # -----------------------------------------------------

        payment_amount = self._safe_float(
            payment_option.get(
                "payment_amount"
            )
        )

        if payment_amount is None:
            return []

        if payment_amount <= 0:
            return []

        # -----------------------------------------------------
        # First payment date
        # -----------------------------------------------------

        first_payment_date = self._normalize_date(
            payment_option.get(
                "first_payment_date"
            )
        )

        if first_payment_date is None:
            return []

        # -----------------------------------------------------
        # Frequency
        # -----------------------------------------------------

        frequency_days = self._safe_float(
            payment_option.get(
                "payment_frequency_days"
            )
        )

        # -----------------------------------------------------
        # Generate dates
        # -----------------------------------------------------

        payment_dates = []

        # One-time payment
        if number_of_payments == 1:

            payment_dates.append(
                first_payment_date
            )

        else:

            if frequency_days is None:
                return []

            if frequency_days <= 0:
                return []

            for payment_number in range(
                number_of_payments
            ):

                payment_date = (
                    first_payment_date
                    + pd.Timedelta(
                        days=(
                            payment_number
                            * frequency_days
                        )
                    )
                )

                payment_dates.append(
                    payment_date.normalize()
                )

        # -----------------------------------------------------
        # Build schedule
        # -----------------------------------------------------

        schedule = []

        for index, payment_date in enumerate(
            payment_dates,
            start=1
        ):

            schedule.append({

                "date": payment_date,

                "amount": payment_amount,

                "payment_number": index,

                "total_payments":
                    number_of_payments,

                "payment_option_id":
                    payment_option.get(
                        "payment_option_id"
                    ),

                "payment_method":
                    payment_option.get(
                        "payment_method"
                    )

            })

        return schedule

    # =========================================================
    # 7. SIMULATE BALANCE
    # =========================================================

    def simulate(
        self,
        end_date,
        additional_payments=None
    ):

        end_date = self._normalize_date(
            end_date
        )

        if end_date is None:
            return pd.DataFrame()

        if additional_payments is None:
            additional_payments = []

        # -----------------------------------------------------
        # Payment dictionary
        # -----------------------------------------------------

        payment_by_date = {}

        for payment in additional_payments:

            if not isinstance(payment, dict):
                continue

            payment_date = self._normalize_date(
                payment.get("date")
            )

            amount = self._safe_float(
                payment.get("amount")
            )

            if payment_date is None:
                continue

            if amount is None or amount <= 0:
                continue

            # Ignore payments before request date
            if payment_date < self.request_date:
                continue

            payment_by_date[payment_date] = (
                payment_by_date.get(
                    payment_date,
                    0.0
                )
                + amount
            )

        # -----------------------------------------------------
        # Cash flows
        # -----------------------------------------------------

        cashflows = self.get_all_cashflows()

        flows_by_date = {}

        for flow in cashflows:

            date = flow["date"]

            # Only simulate until end date
            if date > end_date:
                continue

            if date not in flows_by_date:
                flows_by_date[date] = []

            flows_by_date[date].append(
                flow
            )

        # -----------------------------------------------------
        # Start simulation
        # -----------------------------------------------------

        balance = self.current_balance

        records = []

        current_date = self.request_date

        while current_date <= end_date:

            starting_balance = balance

            income = 0.0
            expenses = 0.0

            # -------------------------------------------------
            # Apply cash flows
            # -------------------------------------------------

            if current_date in flows_by_date:

                for flow in flows_by_date[
                    current_date
                ]:

                    if flow["type"] == "income":

                        income += float(
                            flow["amount"]
                        )

                    elif flow["type"] == "expense":

                        expenses += float(
                            flow["amount"]
                        )

            # -------------------------------------------------
            # Apply requested payment
            # -------------------------------------------------

            payment = payment_by_date.get(
                current_date,
                0.0
            )

            # -------------------------------------------------
            # Calculate balance
            # -------------------------------------------------

            balance += income

            balance -= expenses

            balance -= payment

            # -------------------------------------------------
            # Safety check
            # -------------------------------------------------

            safe = (
                balance >=
                self.minimum_balance
            )

            records.append({

                "date": current_date,

                "starting_balance":
                    starting_balance,

                "income":
                    income,

                "expenses":
                    expenses,

                "payment":
                    payment,

                "ending_balance":
                    balance,

                "safe":
                    safe
            })

            current_date += timedelta(
                days=1
            )

        return pd.DataFrame(
            records
        )

    # =========================================================
    # 8. CHECK PAYMENT PLAN
    # =========================================================

    def check_payment_plan(
        self,
        payments,
        end_date
    ):
        """
        Check whether ALL payments in a payment plan can
        be made while preserving the minimum required balance.
        """

        simulation = self.simulate(
            end_date=end_date,
            additional_payments=payments
        )

        if simulation.empty:

            return {
                "safe": True,

                "minimum_balance_seen":
                    self.current_balance,

                "unsafe_days":
                    0,

                "simulation":
                    simulation
            }

        minimum_balance_seen = (
            simulation[
                "ending_balance"
            ].min()
        )

        unsafe_days = (
            ~simulation["safe"]
        ).sum()

        return {

            "safe":
                unsafe_days == 0,

            "minimum_balance_seen":
                float(
                    minimum_balance_seen
                ),

            "unsafe_days":
                int(
                    unsafe_days
                ),

            "simulation":
                simulation
        }

    # =========================================================
    # 9. CHECK PAYMENT OPTION
    # =========================================================

    def check_payment_option(
        self,
        payment_option,
        end_date
    ):
        """
        Evaluate one payment option produced by PaymentPlanner.

        This is the main integration point between:

            PaymentPlanner
                    ↓
            CashFlowSimulator
        """

        schedule = self.create_payment_schedule(
            payment_option
        )

        if not schedule:

            return {

                "safe": False,

                "reason":
                    "Invalid payment schedule.",

                "payment_option":
                    payment_option,

                "schedule":
                    [],

                "minimum_balance_seen":
                    self.current_balance,

                "unsafe_days":
                    0,

                "simulation":
                    pd.DataFrame()
            }

        # -----------------------------------------------------
        # Validate that final payment is within end date
        # -----------------------------------------------------

        last_payment_date = max(
            payment["date"]
            for payment in schedule
        )

        end_date_normalized = self._normalize_date(
            end_date
        )

        if end_date_normalized is None:

            return {

                "safe": False,

                "reason":
                    "Invalid end date.",

                "payment_option":
                    payment_option,

                "schedule":
                    schedule,

                "minimum_balance_seen":
                    self.current_balance,

                "unsafe_days":
                    0,

                "simulation":
                    pd.DataFrame()
            }

        if last_payment_date > end_date_normalized:

            return {

                "safe": False,

                "reason":
                    "Payment plan finishes after desired completion date.",

                "payment_option":
                    payment_option,

                "schedule":
                    schedule,

                "minimum_balance_seen":
                    self.current_balance,

                "unsafe_days":
                    0,

                "simulation":
                    pd.DataFrame()
            }

        # -----------------------------------------------------
        # Validate no payment is before request date
        # -----------------------------------------------------

        for payment in schedule:

            if payment["date"] < self.request_date:

                return {

                    "safe": False,

                    "reason":
                        "Payment occurs before request date.",

                    "payment_option":
                        payment_option,

                    "schedule":
                        schedule,

                    "minimum_balance_seen":
                        self.current_balance,

                    "unsafe_days":
                        0,

                    "simulation":
                        pd.DataFrame()
                }

        # -----------------------------------------------------
        # Simulate
        # -----------------------------------------------------

        result = self.check_payment_plan(
            payments=schedule,
            end_date=end_date_normalized
        )

        # -----------------------------------------------------
        # Add planner information
        # -----------------------------------------------------

        result["payment_option"] = payment_option

        result["schedule"] = schedule

        result["payment_option_id"] = (
            payment_option.get(
                "payment_option_id"
            )
        )

        result["payment_method"] = (
            payment_option.get(
                "payment_method"
            )
        )

        result["total_payable_amount"] = (
            self._safe_float(
                payment_option.get(
                    "total_payable_amount"
                ),
                0.0
            )
        )

        result["financing_fee"] = (
            self._safe_float(
                payment_option.get(
                    "financing_fee"
                ),
                0.0
            )
        )

        return result

    # =========================================================
    # 10. EVALUATE ALL PAYMENT OPTIONS
    # =========================================================

    def evaluate_payment_options(
        self,
        payment_options,
        end_date
    ):
        """
        Evaluate every valid payment option.

        payment_options can be:
            - list of dictionaries
            - pandas DataFrame
        """

        results = []

        if payment_options is None:
            return results

        # Convert DataFrame to records
        if isinstance(
            payment_options,
            pd.DataFrame
        ):

            payment_options = (
                payment_options
                .to_dict("records")
            )

        for option in payment_options:

            if not isinstance(option, dict):
                continue

            result = self.check_payment_option(
                payment_option=option,
                end_date=end_date
            )

            results.append(result)

        return results

    # =========================================================
    # 11. CHECK FULL PAYMENT
    # =========================================================

    def check_full_payment(
        self,
        requested_amount,
        payment_date,
        end_date
    ):

        requested_amount = self._safe_float(
            requested_amount
        )

        payment_date = self._normalize_date(
            payment_date
        )

        end_date = self._normalize_date(
            end_date
        )

        if (
            requested_amount is None
            or payment_date is None
            or end_date is None
        ):

            return {

                "safe": False,

                "minimum_balance_seen":
                    self.current_balance,

                "unsafe_days":
                    0,

                "simulation":
                    pd.DataFrame()
            }

        payments = [

            {
                "date":
                    payment_date,

                "amount":
                    requested_amount
            }

        ]

        return self.check_payment_plan(
            payments=payments,
            end_date=end_date
        )

    # =========================================================
    # 12. FIND EARLIEST SAFE DATE
    # =========================================================

    def find_earliest_safe_date(
        self,
        requested_amount,
        start_date,
        end_date
    ):

        start_date = self._normalize_date(
            start_date
        )

        end_date = self._normalize_date(
            end_date
        )

        requested_amount = self._safe_float(
            requested_amount
        )

        if (
            start_date is None
            or end_date is None
            or requested_amount is None
        ):
            return None

        current_date = start_date

        while current_date <= end_date:

            result = self.check_full_payment(

                requested_amount=
                    requested_amount,

                payment_date=
                    current_date,

                end_date=
                    end_date
            )

            if result["safe"]:

                return current_date

            current_date += timedelta(
                days=1
            )

        return None

    # =========================================================
    # 13. FIND SAFE AMOUNT FOR A SPECIFIC DATE
    # =========================================================

    def find_safe_amount(
        self,
        payment_date,
        end_date,
        requested_amount
    ):
        """
        Find the maximum amount that can safely be paid
        on a specific date while maintaining the minimum
        balance through end_date.

        Uses binary search.
        """

        payment_date = self._normalize_date(
            payment_date
        )

        end_date = self._normalize_date(
            end_date
        )

        requested_amount = self._safe_float(
            requested_amount
        )

        if (
            payment_date is None
            or end_date is None
            or requested_amount is None
        ):
            return 0.0

        if requested_amount <= 0:
            return 0.0

        # -----------------------------------------------------
        # If full amount is safe, return full amount
        # -----------------------------------------------------

        full_result = self.check_full_payment(
            requested_amount=
                requested_amount,

            payment_date=
                payment_date,

            end_date=
                end_date
        )

        if full_result["safe"]:
            return requested_amount

        # -----------------------------------------------------
        # Check whether even a zero payment is unsafe.
        # -----------------------------------------------------

        zero_result = self.check_full_payment(
            requested_amount=0.0,
            payment_date=payment_date,
            end_date=end_date
        )

        if not zero_result["safe"]:
            return 0.0

        # -----------------------------------------------------
        # Binary search
        # -----------------------------------------------------

        low = 0.0
        high = requested_amount

        # 50 iterations gives more than enough precision
        # for currency amounts.
        for _ in range(50):

            mid = (
                low + high
            ) / 2.0

            result = self.check_full_payment(
                requested_amount=mid,
                payment_date=payment_date,
                end_date=end_date
            )

            if result["safe"]:
                low = mid
            else:
                high = mid

        return round(
            low,
            2
        )


# =============================================================
# TEST / INTEGRATION TEST
# =============================================================

if __name__ == "__main__":

    from data_loader import FinancialDataLoader
    from message_extractor import MessageExtractor
    from forecast_engine import ForecastEngine
    from payment_planner import PaymentPlanner

    request_id = "request_26"

    print("\n" + "=" * 75)
    print("CASH FLOW SIMULATOR + PAYMENT PLANNER")
    print("=" * 75)

    # =========================================================
    # LOAD DATA
    # =========================================================

    loader = FinancialDataLoader()

    context = loader.build_request_context(
        request_id
    )

    request = context["request"]

    profile = context["user_profile"]

    events = pd.DataFrame(
        context.get(
            "financial_events",
            []
        )
    )

    # =========================================================
    # NORMALIZE DATES
    # =========================================================

    request_date = pd.Timestamp(
        request["request_date"]
    ).normalize()

    desired_completion_date = pd.Timestamp(
        request["desired_completion_date"]
    ).normalize()

    # =========================================================
    # MESSAGE EVIDENCE
    # =========================================================

    print("\n" + "=" * 75)
    print("EXTRACTING MESSAGE EVIDENCE")
    print("=" * 75)

    extractor = MessageExtractor(
        context.get(
            "messages",
            []
        )
    )

    message_evidence = (
        extractor.extract_all()
    )

    print(
        "Message evidence found:",
        len(message_evidence)
    )

    for evidence in message_evidence:

        print(evidence)

    # =========================================================
    # FORECAST
    # =========================================================

    print("\n" + "=" * 75)
    print("GENERATING FORECAST")
    print("=" * 75)

    forecast_engine = ForecastEngine(
        context
    )

    forecast = (
        forecast_engine.generate_forecast(
            end_date=
                desired_completion_date.date()
        )
    )

    print(
        "Forecast transactions:",
        len(forecast)
    )

    # =========================================================
    # CREATE SIMULATOR
    # =========================================================

    simulator = CashFlowSimulator(

        current_balance=
            profile[
                "current_available_balance"
            ],

        minimum_balance=
            profile[
                "minimum_balance_to_keep"
            ],

        request_date=
            request_date,

        home_currency=
            profile[
                "home_currency"
            ],

        financial_events=
            events,

        message_evidence=
            message_evidence,

        forecast=
            forecast
    )

    # =========================================================
    # SHOW CASH FLOWS
    # =========================================================

    print("\n" + "=" * 75)
    print("COMBINED CASH FLOW")
    print("=" * 75)

    cashflows = (
        simulator.get_all_cashflows()
    )

    if not cashflows:

        print(
            "No future cash flows found."
        )

    else:

        for flow in cashflows:

            print(

                flow["date"].strftime(
                    "%Y-%m-%d"
                ),

                "|",

                flow["type"],

                "|",

                f"{flow['amount']:,.2f}",

                "|",

                flow["source"],

                "|",

                flow["category"]
            )

    # =========================================================
    # PAYMENT PLANNER
    # =========================================================

    print("\n" + "=" * 75)
    print("PAYMENT PLANNER")
    print("=" * 75)

    planner = PaymentPlanner(
        context,
        simulator=simulator
    )

    # Get valid options
    valid_options = (
        planner.get_valid_payment_options()
    )

    print(
        "Valid payment options:",
        len(valid_options)
    )

    # =========================================================
    # EVALUATE PAYMENT OPTIONS
    # =========================================================

    print("\n" + "=" * 75)
    print("PAYMENT OPTION EVALUATION")
    print("=" * 75)

    option_results = (
        simulator.evaluate_payment_options(
            payment_options=
                valid_options,

            end_date=
                desired_completion_date
        )
    )

    if not option_results:

        print(
            "No valid payment options available."
        )

    else:

        for result in option_results:

            print("\n" + "-" * 75)

            print(
                "Option:",
                result.get(
                    "payment_option_id"
                )
            )

            print(
                "Method:",
                result.get(
                    "payment_method"
                )
            )

            print(
                "Safe:",
                result.get(
                    "safe"
                )
            )

            print(
                "Minimum balance seen:",
                f"{result.get('minimum_balance_seen', 0):,.2f}"
            )

            print(
                "Unsafe days:",
                result.get(
                    "unsafe_days"
                )
            )

            print(
                "Financing fee:",
                f"{result.get('financing_fee', 0):,.2f}"
            )

            print(
                "Total payable:",
                f"{result.get('total_payable_amount', 0):,.2f}"
            )

            print(
                "Payment schedule:"
            )

            for payment in result.get(
                "schedule",
                []
            ):

                print(
                    "  Payment",
                    payment["payment_number"],
                    ":",
                    payment["date"].strftime(
                        "%Y-%m-%d"
                    ),
                    "→",
                    f"{payment['amount']:,.2f}"
                )

    # =========================================================
    # FULL PAYMENT TODAY
    # =========================================================

    requested_amount = float(
        request[
            "requested_amount"
        ]
    )

    print("\n" + "=" * 75)
    print("FULL PAYMENT TODAY")
    print("=" * 75)

    result = simulator.check_full_payment(

        requested_amount=
            requested_amount,

        payment_date=
            request_date,

        end_date=
            desired_completion_date
    )

    print(
        "Safe:",
        result["safe"]
    )

    print(
        "Minimum balance seen:",
        f"{result['minimum_balance_seen']:,.2f}"
    )

    print(
        "Unsafe days:",
        result["unsafe_days"]
    )

    # =========================================================
    # EARLIEST SAFE DATE
    # =========================================================

    print("\n" + "=" * 75)
    print("EARLIEST SAFE DATE")
    print("=" * 75)

    earliest = (
        simulator.find_earliest_safe_date(

            requested_amount=
                requested_amount,

            start_date=
                request_date,

            end_date=
                desired_completion_date
        )
    )

    if earliest is not None:

        print(
            "Earliest safe date:",
            earliest.date()
        )

    else:

        print(
            "Full payment is not safe within the requested period."
        )

    # =========================================================
    # SAFE AMOUNT
    # =========================================================

    print("\n" + "=" * 75)
    print("MAXIMUM SAFE PAYMENT TODAY")
    print("=" * 75)

    safe_amount = (
        simulator.find_safe_amount(

            payment_date=
                request_date,

            end_date=
                desired_completion_date,

            requested_amount=
                requested_amount
        )
    )

    print(
        "Requested amount:",
        f"{requested_amount:,.2f}"
    )

    print(
        "Maximum safe amount:",
        f"{safe_amount:,.2f}"
    )

    print("\n" + "=" * 75)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 75)