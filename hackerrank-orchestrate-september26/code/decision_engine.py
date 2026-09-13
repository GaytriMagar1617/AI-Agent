import pandas as pd

from payment_planner import PaymentPlanner
from cashflow_simulator import CashFlowSimulator


class DecisionEngine:

    VALID_STATUSES = {
        "affordable_now",
        "affordable_with_plan",
        "affordable_later",
        "not_affordable",
    }

    VALID_PAYMENT_METHODS = {
        "full_payment",
        "partial_payment",
        "installments",
        "wait",
        "not_recommended",
    }

    def __init__(
        self,
        context,
        simulator=None,
        payment_planner=None
    ):
        self.context = context or {}

        self.request = (
            self.context.get("request", {})
            or {}
        )

        self.profile = (
            self.context.get("user_profile", {})
            or {}
        )

        # --------------------------------------------------------
        # Request dates
        # --------------------------------------------------------

        self.request_date = self._parse_date(
            self.request.get("request_date")
            or self.request.get("date")
        )

        self.desired_completion_date = self._parse_date(
            self.request.get("desired_completion_date")
            or self.request.get("completion_date")
            or self.request.get("required_by_date")
        )

        # --------------------------------------------------------
        # Requested amount
        # --------------------------------------------------------

        self.requested_amount = (
            self.get_requested_amount()
        )

        # --------------------------------------------------------
        # User financial information
        # --------------------------------------------------------

        self.home_currency = str(
            self.profile.get(
                "home_currency",
                "USD"
            )
        ).strip().upper()

        self.current_balance = self._to_float(
            self.profile.get(
                "current_available_balance",
                0
            )
        )

        self.minimum_balance = self._to_float(
            self.profile.get(
                "minimum_balance",
                0
            )
        )

        # --------------------------------------------------------
        # Financial events
        # --------------------------------------------------------

        events = self.context.get(
            "financial_events",
            []
        )

        if isinstance(events, pd.DataFrame):

            self.financial_events = events.copy()

        elif isinstance(events, list):

            self.financial_events = (
                pd.DataFrame(events)
            )

        elif isinstance(events, dict):

            self.financial_events = (
                pd.DataFrame([events])
            )

        else:

            self.financial_events = (
                pd.DataFrame()
            )

        # --------------------------------------------------------
        # Message evidence
        # --------------------------------------------------------

        message_evidence = self.context.get(
            "message_evidence",
            []
        )

        if message_evidence is None:
            message_evidence = []

        if not isinstance(
            message_evidence,
            list
        ):
            message_evidence = [
                message_evidence
            ]

        self.message_evidence = (
            message_evidence
        )

        # --------------------------------------------------------
        # Forecast
        # --------------------------------------------------------

        forecast = self.context.get(
            "forecast",
            pd.DataFrame()
        )

        if isinstance(
            forecast,
            pd.DataFrame
        ):

            self.forecast = forecast.copy()

        elif isinstance(
            forecast,
            list
        ):

            self.forecast = (
                pd.DataFrame(forecast)
            )

        elif isinstance(
            forecast,
            dict
        ):

            self.forecast = (
                pd.DataFrame([forecast])
            )

        else:

            self.forecast = (
                pd.DataFrame()
            )

        # --------------------------------------------------------
        # PAYMENT PLANNER
        #
        # If the test/pipeline supplies a planner,
        # use it. Otherwise create one.
        # --------------------------------------------------------

        if payment_planner is not None:

            self.payment_planner = (
                payment_planner
            )

        else:

            self.payment_planner = (
                PaymentPlanner(self.context)
            )

        # --------------------------------------------------------
        # CASH FLOW SIMULATOR
        #
        # If the test/pipeline supplies a simulator,
        # use it. Otherwise create one.
        # --------------------------------------------------------

        if simulator is not None:

            self.simulator = simulator

        else:

            self.simulator = (
                CashFlowSimulator(
                    current_balance=(
                        self.current_balance
                    ),
                    minimum_balance=(
                        self.minimum_balance
                    ),
                    request_date=(
                        self.request_date
                    ),
                    home_currency=(
                        self.home_currency
                    ),
                    financial_events=(
                        self.financial_events
                    ),
                    message_evidence=(
                        self.message_evidence
                    ),
                    forecast=(
                        self.forecast
                    ),
                )
            )

        # --------------------------------------------------------
        # Connect planner and simulator
        # --------------------------------------------------------

        try:

            self.payment_planner.simulator = (
                self.simulator
            )

        except Exception:
            pass

    # ============================================================
    # BASIC HELPERS
    # ============================================================

    @staticmethod
    def _to_float(value, default=0.0):

        try:

            if value is None:
                return default

            if isinstance(value, str):
                value = value.replace(",", "").strip()

            value = float(value)

            if pd.isna(value):
                return default

            return value

        except Exception:
            return default

    @staticmethod
    def _parse_date(value):

        if value is None or value == "":
            return None

        try:
            return pd.Timestamp(value).normalize()

        except Exception:
            return None

    @staticmethod
    def _date_string(value):

        if value is None:
            return ""

        try:
            return pd.Timestamp(value).strftime("%Y-%m-%d")

        except Exception:
            return str(value)

    # ============================================================
    # REQUEST INFORMATION
    # ============================================================

    def get_requested_amount(self):

        amount = self.request.get(
            "requested_amount",
            0
        )

        return max(
            0.0,
            self._to_float(amount)
        )

    def accepted_payment_methods(self):

        value = (
            self.profile.get(
                "payment_methods_user_will_consider"
            )
            or self.profile.get(
                "payment_methods"
            )
            or self.profile.get(
                "accepted_payment_methods"
            )
            or []
        )

        if isinstance(value, str):

            values = (
                value
                .replace(";", ",")
                .split(",")
            )

        elif isinstance(value, (list, tuple, set)):

            values = list(value)

        else:

            values = []

        return {
            str(item).strip().lower()
            for item in values
            if str(item).strip()
        }

    def partial_payment_allowed(self):

        fields = [
            "allows_partial_payment",
            "partial_payment_allowed",
            "Partial Payment Allowed",
            "partial_payment",
        ]

        for field in fields:

            if field not in self.request:
                continue

            value = self.request.get(field)

            if isinstance(value, bool):
                return value

            value = str(value).strip().lower()

            if value in {
                "true",
                "yes",
                "y",
                "1",
                "allowed",
            }:
                return True

            if value in {
                "false",
                "no",
                "n",
                "0",
                "not allowed",
            }:
                return False

        return False

    # ============================================================
    # PAYMENT OPTIONS
    # ============================================================

    def get_valid_options(self):

        try:

            options = (
                self.payment_planner
                .get_valid_payment_options()
            )

            if options is None:
                return pd.DataFrame()

            if isinstance(options, pd.DataFrame):
                return options.copy()

            if isinstance(options, list):
                return pd.DataFrame(options)

            if isinstance(options, dict):
                return pd.DataFrame([options])

            return pd.DataFrame()

        except Exception as e:

            print(
                f"Error getting valid payment options: {e}"
            )

            return pd.DataFrame()

    def get_payment_evaluations(self):
        evaluations = []
        options = self.get_valid_options()

        for _, row in options.iterrows():

            try:

                option = row.to_dict()

                payment_method = str(
                    option.get(
                        "payment_method",
                        ""
                    )
                ).strip().lower()

                if not payment_method:

                    payment_method = str(
                        option.get(
                            "method",
                            ""
                        )
                    ).strip().lower()

                try:

                    result = (
                        self.simulator
                        .check_payment_option(
                            option,
                            self.desired_completion_date
                            or self.request_date,
                        )
                    )

                except Exception:

                    result = (
                        self.simulator
                        .check_payment_plan(option)
                    )

                if isinstance(result, dict):

                    safe = bool(
                        result.get("safe")
                        or result.get("is_safe")
                        or result.get("affordable")
                        or result.get("valid")
                    )

                else:

                    safe = bool(result)

                evaluations.append({
                    "option": option,
                    "payment_method": payment_method,
                    "safe": safe,
                    "result": result,
                })

            except Exception as e:

                print(
                    f"Payment evaluation error: {e}"
                )

        return evaluations

    # ============================================================
    # PAYMENT PLAN FORMATTING
    # ============================================================

    def format_payment_plan(
        self,
        payment_method,
        payment_option=None,
        schedule=None,
    ):

        payment_method = (
            str(payment_method)
            .strip()
            .lower()
        )

        option = payment_option or {}

        if isinstance(option, pd.Series):
            option = option.to_dict()

        # --------------------------------------------------------
        # FULL PAYMENT
        # --------------------------------------------------------

        if payment_method == "full_payment":

            date = self.request_date

            if schedule is not None:

                dates = self._extract_schedule_dates(
                    schedule
                )

                if dates:
                    date = dates[0]

            return (
                f"Full payment of "
                f"{self.requested_amount:.2f} "
                f"on {self._date_string(date)}"
            )

        # --------------------------------------------------------
        # INSTALLMENTS
        # --------------------------------------------------------

        if payment_method == "installments":

            number = self._to_float(
                option.get(
                    "number_of_payments",
                    0
                )
            )

            installment_amount = self._to_float(
                option.get(
                    "installment_amount",
                    0
                )
            )

            frequency = self._to_float(
                option.get(
                    "payment_frequency_days",
                    option.get(
                        "frequency_days",
                        30
                    ),
                ),
                30,
            )

            first_date = (
                option.get(
                    "first_payment_date"
                )
                or option.get(
                    "start_date"
                )
                or self.request_date
            )

            total_payable = self._to_float(
                option.get(
                    "total_payable",
                    option.get(
                        "total_amount",
                        0
                    ),
                )
            )

            fee = self._to_float(
                option.get(
                    "financing_fee",
                    option.get(
                        "fee",
                        0
                    ),
                )
            )

            if number.is_integer():
                number_text = str(int(number))
            else:
                number_text = str(number)

            return (
                f"{number_text} installments of "
                f"{installment_amount:.2f}, starting "
                f"{self._date_string(first_date)}, every "
                f"{int(frequency)} days; total payable "
                f"{total_payable:.2f}; financing fee "
                f"{fee:.2f}"
            )

        # --------------------------------------------------------
        # PARTIAL PAYMENT
        # --------------------------------------------------------

        if payment_method == "partial_payment":

            safe_amount = self._to_float(
                option.get(
                    "first_payment_amount",
                    option.get(
                        "partial_amount",
                        option.get(
                            "amount",
                            0
                        ),
                    ),
                )
            )

            second_amount = (
                self.requested_amount
                - safe_amount
            )

            dates = self._extract_schedule_dates(
                schedule
            )

            if len(dates) >= 2:

                first_date = dates[0]
                second_date = dates[1]

            else:

                first_date = self.request_date
                second_date = (
                    self.desired_completion_date
                )

            return (
                f"Partial payment of "
                f"{safe_amount:.2f} on "
                f"{self._date_string(first_date)}, "
                f"followed by "
                f"{second_amount:.2f} on "
                f"{self._date_string(second_date)}"
            )

        return ""

    # ============================================================
    # SCHEDULE HELPERS
    # ============================================================

    def _extract_schedule_dates(self, schedule):

        dates = []

        if schedule is None:
            return dates

        # DataFrame
        if isinstance(schedule, pd.DataFrame):

            for column in [
                "date",
                "payment_date",
                "scheduled_date",
            ]:

                if column in schedule.columns:

                    for value in schedule[column].tolist():

                        parsed = self._parse_date(value)

                        if parsed is not None:
                            dates.append(parsed)

                    if dates:
                        return sorted(dates)

        # List
        elif isinstance(schedule, list):

            for item in schedule:

                if isinstance(item, dict):

                    value = (
                        item.get("date")
                        or item.get("payment_date")
                        or item.get("scheduled_date")
                    )

                else:

                    value = item

                parsed = self._parse_date(value)

                if parsed is not None:
                    dates.append(parsed)

        # Dictionary
        elif isinstance(schedule, dict):

            for key in [
                "date",
                "payment_date",
                "scheduled_date",
                "dates",
                "payment_dates",
            ]:

                if key not in schedule:
                    continue

                value = schedule[key]

                if isinstance(value, list):

                    for item in value:

                        parsed = self._parse_date(item)

                        if parsed is not None:
                            dates.append(parsed)

                else:

                    parsed = self._parse_date(value)

                    if parsed is not None:
                        dates.append(parsed)

                if dates:
                    break

        return sorted(dates)

    def get_final_payment_date(self, schedule):

        dates = self._extract_schedule_dates(
            schedule
        )

        if not dates:
            return None

        return max(dates)

    # ============================================================
    # FULL PAYMENT
    # ============================================================

    def find_safe_full_payment(self):
        try:
            payment_date = self.request_date
            end_date = self.desired_completion_date or self.request_date

            result = self.simulator.check_full_payment(
                self.requested_amount,
                payment_date,
                end_date
            )

            if isinstance(result, dict):
                return bool(
                    result.get("safe")
                    or result.get("is_safe")
                    or result.get("affordable")
                    or result.get("valid")
                )

            return bool(result)

        except Exception as e:
            print(f"Full payment check error: {e}")
            return False

    # ============================================================
    # INSTALLMENTS
    # ============================================================

    def find_safe_installment(self):

        options = self.get_valid_options()

        if options.empty:
            return None

        accepted = self.accepted_payment_methods()

        for _, row in options.iterrows():

            option = row.to_dict()

            method = str(
                option.get(
                    "payment_method",
                    ""
                )
            ).strip().lower()

            if not method:

                method = str(
                    option.get(
                        "method",
                        ""
                    )
                ).strip().lower()

            if method != "installments":
                continue

            if (
                accepted
                and "installments" not in accepted
            ):
                continue

            try:

                result = (
                    self.simulator
                    .check_payment_option(option)
                )

                if isinstance(result, dict):

                    safe = bool(
                        result.get("safe")
                        or result.get("is_safe")
                        or result.get("affordable")
                        or result.get("valid")
                    )

                else:

                    safe = bool(result)

                if safe:
                    return option

            except Exception as e:

                print(
                    f"Installment check error: {e}"
                )

        return None

    # ============================================================
    # EARLIEST SAFE DATE
    # ============================================================

    def get_earliest_safe_date(self):

        if self.requested_amount <= 0:
            return self.request_date

        try:

            start_date = self.request_date

            end_date = (
                self.desired_completion_date
                or self.request_date
            )

            result = self.simulator.find_earliest_safe_date(
                self.requested_amount,
                start_date,
                end_date
            )

            return self._parse_date(result)

        except Exception as e:

            print(
                f"Earliest safe date error: {e}"
            )

            return None

    # ============================================================
    # MAXIMUM SAFE AMOUNT
    # ============================================================

    def get_max_safe_amount(self):

        if self.requested_amount <= 0:
            return 0.0

        try:

            result = (
                self.simulator
                .find_safe_amount(
                    self.requested_amount
                )
            )

            if isinstance(result, dict):

                amount = (
                    result.get("safe_amount")
                    or result.get("amount")
                    or result.get("max_safe_amount")
                    or 0
                )

            else:

                amount = result

            amount = self._to_float(amount)

            return max(
                0.0,
                min(
                    self.requested_amount,
                    amount
                ),
            )

        except TypeError:

            try:

                result = (
                    self.simulator
                    .find_safe_amount()
                )

                amount = self._to_float(result)

                return max(
                    0.0,
                    min(
                        self.requested_amount,
                        amount
                    ),
                )

            except Exception as e:

                print(
                    f"Maximum safe amount error: {e}"
                )

                return 0.0

        except Exception as e:

            print(
                f"Maximum safe amount error: {e}"
            )

            return 0.0

    # ============================================================
    # PARTIAL PAYMENT
    # ============================================================

    def evaluate_partial_payment(self):

        accepted = self.accepted_payment_methods()

        if "partial_payment" not in accepted:
            return None

        if not self.partial_payment_allowed():
            return None

        if self.requested_amount <= 0:
            return None

        if self.desired_completion_date is None:
            return None

        safe_amount = self.get_max_safe_amount()

        if safe_amount <= 0:
            return None

        if safe_amount >= self.requested_amount:
            return None

        second_amount = (
            self.requested_amount - safe_amount
        )

        if second_amount <= 0:
            return None

        schedule = [
            {
                "date": self.request_date,
                "amount": safe_amount,
            },
            {
                "date": self.desired_completion_date,
                "amount": second_amount,
            },
        ]

        try:

            result = self.simulator.simulate(
                self.desired_completion_date,
                schedule
            )

            if isinstance(result, dict):

                safe = bool(
                    result.get("safe")
                    or result.get("is_safe")
                    or result.get("affordable")
                )

            else:
                safe = bool(result)

            if not safe:
                return None

        except Exception as e:

            print(
                f"Partial payment simulation error: {e}"
            )

            return None

        return {
            "safe_amount": safe_amount,
            "second_amount": second_amount,
            "schedule": schedule,
            "final_date": self.desired_completion_date,
        }

    # ============================================================
    # SPENDING CHANGES
    # ============================================================

    def get_spending_changes(self):

        changes = []

        reduce_categories = self.profile.get(
            "expense_categories_user_is_willing_to_reduce",
            []
        )

        stop_categories = self.profile.get(
            "expense_categories_user_is_willing_to_stop",
            []
        )

        if isinstance(
            reduce_categories,
            str
        ):

            reduce_categories = [
                x.strip()
                for x in (
                    reduce_categories
                    .replace(";", ",")
                    .split(",")
                )
                if x.strip()
            ]

        if isinstance(
            stop_categories,
            str
        ):

            stop_categories = [
                x.strip()
                for x in (
                    stop_categories
                    .replace(";", ",")
                    .split(",")
                )
                if x.strip()
            ]

        for category in reduce_categories:

            category = str(category).strip()

            if category:

                text = (
                    f"Reduce {category}"
                )

                if text not in changes:
                    changes.append(text)

        for category in stop_categories:

            category = str(category).strip()

            if category:

                text = (
                    f"Stop {category}"
                )

                if text not in changes:
                    changes.append(text)

        return changes

    # ============================================================
    # EXPLANATION
    # ============================================================

    def build_explanation(
        self,
        status,
        payment_method,
        payment_plan="",
        final_date=None,
        spending_changes=None,
    ):

        amount = self.requested_amount

        spending_changes = (
            spending_changes or []
        )

        if status == "affordable_now":

            return (
                f"The full requested amount of "
                f"{amount:.2f} can be paid safely "
                f"while maintaining the required "
                f"minimum balance. The recommended "
                f"method is "
                f"{payment_method.replace('_', ' ')}."
            )

        if status == "affordable_with_plan":

            date_text = self._date_string(
                final_date
            )

            return (
                "The full amount is not safely "
                "available as a single payment, "
                "but the supplied payment plan "
                "keeps the balance above the "
                "required minimum. "
                f"The plan completes by "
                f"{date_text}."
            )

        if status == "affordable_later":

            date_text = self._date_string(
                final_date
            )

            return (
                "The requested amount is not "
                "safely available today, but "
                "the full amount can be paid "
                "later while maintaining the "
                "required minimum balance. "
                f"The earliest safe date is "
                f"{date_text}."
            )

        if spending_changes:

            return (
                "The requested payment cannot "
                "be made safely within the "
                "required period while "
                "maintaining the required "
                "minimum balance. Flexible "
                "spending changes such as "
                + ", ".join(spending_changes)
                + " may help reduce expenses, "
                "but there is still no safe "
                "payment plan within the "
                "available options."
            )

        return (
            "The requested payment cannot "
            "be made safely within the "
            "required period while maintaining "
            "the required minimum balance. "
            "No valid payment option is safe."
        )

    # ============================================================
    # MAIN DECISION
    # ============================================================

    def decide(self):

        amount = self.requested_amount

        # --------------------------------------------------------
        # INVALID / ZERO AMOUNT
        # --------------------------------------------------------

        if amount <= 0:

            return {
                "request_id": self.request.get(
                    "request_id",
                    ""
                ),
                "amount_safe_to_pay": 0.0,
                "affordability_status": (
                    "not_affordable"
                ),
                "recommended_payment_method": (
                    "not_recommended"
                ),
                "payment_plan": "",
                "earliest_date_for_full_payment": "",
                "spending_changes_needed": "",
                "decision_explanation": (
                    "The requested amount is zero "
                    "or invalid, so no payment is "
                    "recommended."
                ),
            }

        accepted = (
            self.accepted_payment_methods()
        )

        # --------------------------------------------------------
        # 1. FULL PAYMENT
        # --------------------------------------------------------

        if (
            not accepted
            or "full_payment" in accepted
        ):

            if self.find_safe_full_payment():

                payment_plan = (
                    self.format_payment_plan(
                        "full_payment"
                    )
                )

                return {
                    "request_id": self.request.get(
                        "request_id",
                        ""
                    ),
                    "amount_safe_to_pay": round(
                        amount,
                        2
                    ),
                    "affordability_status": (
                        "affordable_now"
                    ),
                    "recommended_payment_method": (
                        "full_payment"
                    ),
                    "payment_plan": payment_plan,
                    "earliest_date_for_full_payment": (
                        self._date_string(
                            self.request_date
                        )
                    ),
                    "spending_changes_needed": "",
                    "decision_explanation": (
                        self.build_explanation(
                            "affordable_now",
                            "full_payment",
                            payment_plan=payment_plan,
                            final_date=self.request_date,
                        )
                    ),
                }

        # --------------------------------------------------------
        # 2. INSTALLMENTS
        # --------------------------------------------------------

        installment = None

        if (
            not accepted
            or "installments" in accepted
        ):

            installment = (
                self.find_safe_installment()
            )

        if installment is not None:

            try:

                schedule = (
                    self.payment_planner
                    .generate_payment_dates(
                        installment
                    )
                )

            except Exception:

                schedule = None

            final_date = (
                self.get_final_payment_date(
                    schedule
                )
            )

            if final_date is None:

                final_date = (
                    self._parse_date(
                        installment.get(
                            "last_payment_date"
                        )
                        or installment.get(
                            "final_payment_date"
                        )
                    )
                )

            payment_plan = (
                self.format_payment_plan(
                    "installments",
                    installment,
                    schedule,
                )
            )

            return {
                "request_id": self.request.get(
                    "request_id",
                    ""
                ),
                "amount_safe_to_pay": round(
                    amount,
                    2
                ),
                "affordability_status": (
                    "affordable_with_plan"
                ),
                "recommended_payment_method": (
                    "installments"
                ),
                "payment_plan": payment_plan,
                "earliest_date_for_full_payment": "",
                "spending_changes_needed": "",
                "decision_explanation": (
                    self.build_explanation(
                        "affordable_with_plan",
                        "installments",
                        payment_plan=payment_plan,
                        final_date=final_date,
                    )
                ),
            }

        # --------------------------------------------------------
        # 3. PARTIAL PAYMENT
        # --------------------------------------------------------

        partial = None

        if (
            not accepted
            or "partial_payment" in accepted
        ):

            partial = (
                self.evaluate_partial_payment()
            )

        if partial is not None:

            payment_plan = (
                self.format_payment_plan(
                    "partial_payment",
                    {
                        "first_payment_amount":
                            partial[
                                "safe_amount"
                            ]
                    },
                    partial["schedule"],
                )
            )

            return {
                "request_id": self.request.get(
                    "request_id",
                    ""
                ),
                "amount_safe_to_pay": round(
                    partial["safe_amount"],
                    2,
                ),
                "affordability_status": (
                    "affordable_with_plan"
                ),
                "recommended_payment_method": (
                    "partial_payment"
                ),
                "payment_plan": payment_plan,
                "earliest_date_for_full_payment": "",
                "spending_changes_needed": "",
                "decision_explanation": (
                    f"The full amount of "
                    f"{amount:.2f} is not safely "
                    f"available immediately, "
                    f"but "
                    f"{partial['safe_amount']:.2f} "
                    f"can be paid now and the "
                    f"remaining "
                    f"{partial['second_amount']:.2f} "
                    f"can be paid by "
                    f"{self._date_string(partial['final_date'])}."
                ),
            }

        # --------------------------------------------------------
        # 4. WAIT / PAY LATER
        # --------------------------------------------------------

        earliest_date = (
            self.get_earliest_safe_date()
        )

        if earliest_date is not None:

            if (
                self.desired_completion_date
                is None
                or earliest_date
                <= self.desired_completion_date
            ):

                return {
                    "request_id": self.request.get(
                        "request_id",
                        ""
                    ),
                    "amount_safe_to_pay": 0.0,
                    "affordability_status": (
                        "affordable_later"
                    ),
                    "recommended_payment_method": (
                        "wait"
                    ),
                    "payment_plan": "",
                    "earliest_date_for_full_payment": (
                        self._date_string(
                            earliest_date
                        )
                    ),
                    "spending_changes_needed": "",
                    "decision_explanation": (
                        self.build_explanation(
                            "affordable_later",
                            "wait",
                            final_date=earliest_date,
                        )
                    ),
                }

        # --------------------------------------------------------
        # 5. NOT AFFORDABLE
        # --------------------------------------------------------

        spending_changes = (
            self.get_spending_changes()
        )

        return {
            "request_id": self.request.get(
                "request_id",
                ""
            ),
            "amount_safe_to_pay": 0.0,
            "affordability_status": (
                "not_affordable"
            ),
            "recommended_payment_method": (
                "not_recommended"
            ),
            "payment_plan": "",
            "earliest_date_for_full_payment": "",
            "spending_changes_needed": (
                "; ".join(
                    spending_changes
                )
            ),
            "decision_explanation": (
                self.build_explanation(
                    "not_affordable",
                    "not_recommended",
                    spending_changes=spending_changes,
                )
            ),
        }