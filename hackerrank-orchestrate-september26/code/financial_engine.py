"""
financial_engine.py

Stage 2 of the Buy or Wait? AI Financial Agent.

Purpose:
    Analyze a user's financial situation and calculate whether
    a requested expense can be safely paid.

Important:
    This file performs numerical/financial calculations.
    We will NOT ask an LLM to perform these calculations.

Architecture:

    data_loader.py
          |
          v
    Financial Context
          |
          v
    financial_engine.py
          |
          v
    Financial Forecast
          |
          v
    Payment Plan Decision
"""

from pathlib import Path
from datetime import timedelta
import pandas as pd

from data_loader import FinancialDataLoader


# ============================================================
# FINANCIAL ENGINE
# ============================================================

class FinancialEngine:

    def __init__(self, context):
        """
        Initialize the financial engine with the context
        retrieved by FinancialDataLoader.
        """

        self.context = context

        self.request = context["request"]
        self.profile = context["user_profile"]
        self.events = context["financial_events"]
        self.payment_options = context["payment_options"]

        # ----------------------------------------------------
        # Basic user information
        # ----------------------------------------------------

        self.user_id = self.request["user_id"]

        self.request_date = pd.to_datetime(
            self.request["request_date"]
        ).date()

        self.requested_amount = float(
            self.request["requested_amount"]
        )

        self.home_currency = self.profile["home_currency"]

        self.minimum_balance = float(
            self.profile["minimum_balance_to_keep"]
        )

        self.current_balance = float(
            self.profile["current_available_balance"]
        )

        # ----------------------------------------------------
        # Protected and flexible categories
        # ----------------------------------------------------

        self.protected_categories = self._split_categories(
            self.profile.get(
                "expense_categories_to_protect",
                ""
            )
        )

        self.reduce_categories = self._split_categories(
            self.profile.get(
                "expense_categories_user_is_willing_to_reduce",
                ""
            )
        )

        self.stop_categories = self._split_categories(
            self.profile.get(
                "expense_categories_user_is_willing_to_stop",
                ""
            )
        )


    # ========================================================
    # HELPER: SPLIT CATEGORY STRING
    # ========================================================

    def _split_categories(self, value):
        """
        Convert:

            "rent|utilities|groceries"

        into:

            ["rent", "utilities", "groceries"]
        """

        if value is None:
            return []

        if pd.isna(value):
            return []

        return [
            item.strip().lower()
            for item in str(value).split("|")
            if item.strip()
        ]


    # ========================================================
    # 1. GET FUTURE EVENTS
    # ========================================================

    def get_future_events(self):
        """
        Return financial events occurring after the request date.

        Historical settled transactions should not be counted
        again in the future forecast.
        """

        if not self.events:
            return []

        df = pd.DataFrame(self.events)

        if "event_date" not in df.columns:
            return []

        df["event_date"] = pd.to_datetime(
            df["event_date"],
            errors="coerce"
        )

        request_timestamp = pd.Timestamp(
            self.request_date
        )

        # Only events after request date
        df = df[
            df["event_date"] > request_timestamp
        ].copy()

        # Remove rows without valid dates
        df = df[
            df["event_date"].notna()
        ]

        return df.to_dict(
            orient="records"
        )


    # ========================================================
    # 2. GET EVENTS BETWEEN TWO DATES
    # ========================================================

    def get_events_between(
        self,
        start_date,
        end_date
    ):
        """
        Return events between two dates.
        """

        events = self.get_future_events()

        selected = []

        for event in events:

            event_date = pd.to_datetime(
                event["event_date"]
            ).date()

            if start_date <= event_date <= end_date:
                selected.append(event)

        return selected


    # ========================================================
    # 3. CLASSIFY EVENT
    # ========================================================

    def classify_event(self, event):
        """
        Determine whether an event is income or expense.
        """

        direction = str(
            event.get("direction", "")
        ).lower()

        event_type = str(
            event.get("event_type", "")
        ).lower()

        # Credit = money coming in
        if direction == "credit":
            return "income"

        # Debit = money going out
        if direction == "debit":
            return "expense"

        # Fallback
        if event_type in [
            "income",
            "salary",
            "refund"
        ]:
            return "income"

        return "expense"


    # ========================================================
    # 4. CHECK WHETHER EVENT IS FLEXIBLE
    # ========================================================

    def is_flexible_event(self, event):
        """
        Determine whether an expense can potentially be reduced
        or stopped.

        We use BOTH:
            - event flexibility
            - user's personal preferences
        """

        category = str(
            event.get("category", "")
        ).lower()

        flexibility = str(
            event.get("flexibility", "")
        ).lower()

        # User explicitly wants to stop it
        if category in self.stop_categories:
            return True

        # User explicitly allows reduction
        if category in self.reduce_categories:
            return True

        # Dataset says it is flexible
        if flexibility in [
            "reducible",
            "reducible_or_stoppable",
            "flexible"
        ]:
            return True

        return False


    # ========================================================
    # 5. CHECK WHETHER EVENT IS PROTECTED
    # ========================================================

    def is_protected_event(self, event):
        """
        Determine whether the expense belongs to a protected
        category such as rent, utilities or groceries.
        """

        category = str(
            event.get("category", "")
        ).lower()

        return category in self.protected_categories


    # ========================================================
    # 6. CALCULATE FUTURE INCOME
    # ========================================================

    def calculate_future_income(
        self,
        start_date=None,
        end_date=None
    ):
        """
        Calculate confirmed structured income within a date range.
        """

        if start_date is None:
            start_date = self.request_date

        if end_date is None:
            end_date = self.request_date + timedelta(
                days=90
            )

        events = self.get_events_between(
            start_date,
            end_date
        )

        total = 0.0

        for event in events:

            if self.classify_event(event) == "income":

                amount = float(
                    event.get("amount", 0)
                )

                # For now we only use the user's home currency.
                # Currency conversion will be added later.
                currency = str(
                    event.get("currency", "")
                )

                if currency == self.home_currency:

                    total += amount

        return total


    # ========================================================
    # 7. CALCULATE FUTURE EXPENSES
    # ========================================================

    def calculate_future_expenses(
        self,
        start_date=None,
        end_date=None
    ):
        """
        Calculate future expenses.

        Returns:
            total expenses
            protected expenses
            flexible expenses
        """

        if start_date is None:
            start_date = self.request_date

        if end_date is None:
            end_date = self.request_date + timedelta(
                days=90
            )

        events = self.get_events_between(
            start_date,
            end_date
        )

        total = 0.0
        protected = 0.0
        flexible = 0.0

        for event in events:

            if self.classify_event(event) != "expense":
                continue

            amount = float(
                event.get("amount", 0)
            )

            currency = str(
                event.get("currency", "")
            )

            if currency != self.home_currency:
                continue

            total += amount

            if self.is_protected_event(event):
                protected += amount

            elif self.is_flexible_event(event):
                flexible += amount

        return {
            "total": total,
            "protected": protected,
            "flexible": flexible
        }


    # ========================================================
    # 8. CALCULATE SAFE AMOUNT TODAY
    # ========================================================

    def calculate_safe_amount_today(
        self,
        forecast_days=90
    ):
        """
        Calculate the maximum amount that can safely be paid today.

        Basic formula:

            current balance
            + future confirmed income
            - future essential expenses
            - minimum required balance

        We also consider future flexible expenses.

        The result is the amount that can be spent while
        maintaining the user's minimum balance.
        """

        end_date = (
            self.request_date
            + timedelta(days=forecast_days)
        )

        future_income = self.calculate_future_income(
            self.request_date,
            end_date
        )

        expenses = self.calculate_future_expenses(
            self.request_date,
            end_date
        )

        # ----------------------------------------------------
        # Conservative calculation
        # ----------------------------------------------------

        safe_amount = (
            self.current_balance
            + future_income
            - expenses["total"]
            - self.minimum_balance
        )

        # Safe amount cannot be negative
        safe_amount = max(
            0.0,
            safe_amount
        )

        return {
            "current_balance": self.current_balance,
            "future_income": future_income,
            "future_expenses": expenses["total"],
            "protected_expenses": expenses["protected"],
            "flexible_expenses": expenses["flexible"],
            "minimum_balance": self.minimum_balance,
            "amount_safe_to_pay": safe_amount
        }


    # ========================================================
    # 9. CHECK FULL PAYMENT TODAY
    # ========================================================

    def check_full_payment_today(self):
        """
        Determine whether the requested amount can be paid today.
        """

        result = self.calculate_safe_amount_today()

        safe_amount = result[
            "amount_safe_to_pay"
        ]

        can_afford = (
            self.requested_amount
            <= safe_amount
        )

        return {
            "can_afford": can_afford,
            "requested_amount": self.requested_amount,
            "safe_amount": safe_amount,
            "remaining_safe_margin": (
                safe_amount
                - self.requested_amount
            )
        }


    # ========================================================
    # 10. ANALYZE PAYMENT OPTIONS
    # ========================================================

    def analyze_payment_options(self):
        """
        Evaluate every payment option supplied in the dataset.

        IMPORTANT:
            We do not invent payment options.
            We only analyze the options provided by the contest.
        """

        results = []

        for option in self.payment_options:

            method = str(
                option.get(
                    "payment_method",
                    ""
                )
            )

            amount = float(
                option.get(
                    "payment_amount",
                    0
                )
            )

            number_of_payments = int(
                float(
                    option.get(
                        "number_of_payments",
                        1
                    )
                )
            )

            total_payable = float(
                option.get(
                    "total_payable_amount",
                    amount
                )
            )

            financing_fee = float(
                option.get(
                    "financing_fee",
                    0
                )
            )

            first_payment_date = (
                option.get(
                    "first_payment_date"
                )
            )

            frequency = option.get(
                "payment_frequency_days"
            )

            if pd.isna(frequency):
                frequency = 0
            else:
                frequency = int(
                    float(frequency)
                )

            # ------------------------------------------------
            # Create payment dates
            # ------------------------------------------------

            payment_dates = []

            if pd.notna(first_payment_date):

                first_date = pd.to_datetime(
                    first_payment_date
                ).date()

                for i in range(
                    number_of_payments
                ):

                    payment_date = (
                        first_date
                        + timedelta(
                            days=i * frequency
                        )
                    )

                    payment_dates.append(
                        {
                            "date": str(
                                payment_date
                            ),
                            "amount": amount
                        }
                    )

            results.append(
                {
                    "payment_option_id":
                        option.get(
                            "payment_option_id"
                        ),

                    "payment_method":
                        method,

                    "payment_amount":
                        amount,

                    "number_of_payments":
                        number_of_payments,

                    "financing_fee":
                        financing_fee,

                    "total_payable_amount":
                        total_payable,

                    "payment_dates":
                        payment_dates
                }
            )

        return results


    # ========================================================
    # 11. PRINT FINANCIAL ANALYSIS
    # ========================================================

    def print_analysis(self):

        print("\n")
        print("=" * 80)
        print("FINANCIAL ANALYSIS")
        print("=" * 80)

        print(
            f"User ID:              {self.user_id}"
        )

        print(
            f"Request date:         {self.request_date}"
        )

        print(
            f"Home currency:        {self.home_currency}"
        )

        print(
            f"Current balance:      "
            f"{self.current_balance:,.2f}"
        )

        print(
            f"Minimum balance:      "
            f"{self.minimum_balance:,.2f}"
        )

        print(
            f"Requested amount:     "
            f"{self.requested_amount:,.2f}"
        )

        # ----------------------------------------------------
        # Safe amount
        # ----------------------------------------------------

        safe = self.calculate_safe_amount_today()

        print("\n")
        print("-" * 80)
        print("90-DAY FORECAST")
        print("-" * 80)

        print(
            f"Future income:        "
            f"{safe['future_income']:,.2f}"
        )

        print(
            f"Future expenses:      "
            f"{safe['future_expenses']:,.2f}"
        )

        print(
            f"Protected expenses:   "
            f"{safe['protected_expenses']:,.2f}"
        )

        print(
            f"Flexible expenses:    "
            f"{safe['flexible_expenses']:,.2f}"
        )

        print(
            f"Amount safe today:    "
            f"{safe['amount_safe_to_pay']:,.2f}"
        )

        # ----------------------------------------------------
        # Full payment
        # ----------------------------------------------------

        full_payment = (
            self.check_full_payment_today()
        )

        print("\n")
        print("-" * 80)
        print("FULL PAYMENT TODAY")
        print("-" * 80)

        print(
            f"Can afford:           "
            f"{full_payment['can_afford']}"
        )

        print(
            f"Safe amount:          "
            f"{full_payment['safe_amount']:,.2f}"
        )

        print(
            f"Requested amount:     "
            f"{full_payment['requested_amount']:,.2f}"
        )

        print(
            f"Remaining margin:     "
            f"{full_payment['remaining_safe_margin']:,.2f}"
        )

        # ----------------------------------------------------
        # Payment options
        # ----------------------------------------------------

        print("\n")
        print("-" * 80)
        print("AVAILABLE PAYMENT OPTIONS")
        print("-" * 80)

        options = (
            self.analyze_payment_options()
        )

        for option in options:

            print("\n")

            print(
                f"Option:               "
                f"{option['payment_option_id']}"
            )

            print(
                f"Method:               "
                f"{option['payment_method']}"
            )

            print(
                f"Payment amount:       "
                f"{option['payment_amount']:,.2f}"
            )

            print(
                f"Number of payments:  "
                f"{option['number_of_payments']}"
            )

            print(
                f"Financing fee:        "
                f"{option['financing_fee']:,.2f}"
            )

            print(
                f"Total payable:        "
                f"{option['total_payable_amount']:,.2f}"
            )

            print("Payment dates:")

            for payment in option["payment_dates"]:

                print(
                    f"    {payment['date']} "
                    f"→ {payment['amount']:,.2f}"
                )

        print("\n")
        print("=" * 80)
        print("FINANCIAL ANALYSIS COMPLETE")
        print("=" * 80)


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():

    # --------------------------------------------------------
    # Request ID
    # --------------------------------------------------------

    request_id = "request_26"

    print("\n")
    print("=" * 80)
    print(
        f"ANALYZING {request_id}"
    )
    print("=" * 80)

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    loader = FinancialDataLoader()

    # --------------------------------------------------------
    # Build context
    # --------------------------------------------------------

    context = (
        loader.build_request_context(
            request_id
        )
    )

    # --------------------------------------------------------
    # Create financial engine
    # --------------------------------------------------------

    engine = FinancialEngine(
        context
    )

    # --------------------------------------------------------
    # Analyze
    # --------------------------------------------------------

    engine.print_analysis()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()