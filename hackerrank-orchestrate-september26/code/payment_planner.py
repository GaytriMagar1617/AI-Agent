import pandas as pd
import sys


class PaymentPlanner:

    def __init__(self, context, simulator=None):
        """
        context   : Request context created by FinancialDataLoader
        simulator : CashFlowSimulator object (will be connected later)
        """

        self.context = context
        self.simulator = simulator

        # =====================================================
        # REQUEST INFORMATION
        # =====================================================

        self.request = context["request"]

        self.request_id = self.request["request_id"]

        self.requested_amount = float(
            self.request["requested_amount"]
        )

        # =====================================================
        # USER PROFILE
        # =====================================================

        self.profile = context["user_profile"]

        self.allowed_methods = self._split_categories(
            self.profile.get(
                "payment_methods_user_will_consider",
                ""
            )
        )

        self.max_installment_months = self._to_float(
            self.profile.get(
                "max_installment_months"
            )
        )

    # =========================================================
    # UTILITY FUNCTIONS
    # =========================================================

    def _split_categories(self, value):
        """
        Convert pipe-separated values such as:

        full_payment|installments

        into:

        {'full_payment', 'installments'}
        """

        if value is None or pd.isna(value):
            return set()

        return {
            item.strip().lower()
            for item in str(value).split("|")
            if item.strip()
        }

    # ---------------------------------------------------------

    def _to_float(self, value):
        """
        Safely convert a value to float.
        """

        try:

            if value is None or pd.isna(value):
                return None

            return float(value)

        except (ValueError, TypeError):

            return None

    # =========================================================
    # GET PAYMENT OPTIONS
    # =========================================================

    def get_payment_options(self):
        """
        Get payment options belonging to the current request.
        """

        options = self.context.get("payment_options")

        if options is None:
            return pd.DataFrame()

        if not isinstance(options, pd.DataFrame):
            options = pd.DataFrame(options)

        options = options.copy()

        # -----------------------------------------------------
        # Extra safety: make sure only this request's options
        # are used.
        # -----------------------------------------------------

        if "request_id" in options.columns:

            options = options[
                options["request_id"].astype(str)
                == str(self.request_id)
            ].copy()

        return options

    # =========================================================
    # FILTER USER-ALLOWED METHODS
    # =========================================================

    def filter_allowed_methods(self, options):
        """
        Keep only payment methods that the user is willing
        to consider.
        """

        if options.empty:
            return options

        if "payment_method" not in options.columns:
            return pd.DataFrame(columns=options.columns)

        return options[
            options["payment_method"]
            .astype(str)
            .str.lower()
            .isin(self.allowed_methods)
        ].copy()

    # =========================================================
    # INSTALLMENT VALIDATION
    # =========================================================

    def validate_installment_months(self, row):
        """
        Check whether an installment option is within the
        user's maximum allowed installment duration.

        The dataset provides number_of_payments, which we use
        as the installment duration for contest validation.
        """

        method = str(
            row.get("payment_method", "")
        ).strip().lower()

        # Full payment does not have an installment limit.
        if method != "installments":
            return True

        # If user has no maximum specified,
        # don't reject based on duration.
        if self.max_installment_months is None:
            return True

        number_of_payments = self._to_float(
            row.get("number_of_payments")
        )

        if number_of_payments is None:
            return False

        return (
            number_of_payments
            <= self.max_installment_months
        )

    # =========================================================
    # FILTER INSTALLMENT OPTIONS
    # =========================================================

    def filter_valid_installments(self, options):
        """
        Remove installment plans that exceed the user's
        maximum allowed duration.
        """

        if options.empty:
            return options

        valid_rows = []

        for _, row in options.iterrows():

            if self.validate_installment_months(row):

                valid_rows.append(row)

        if not valid_rows:

            return pd.DataFrame(
                columns=options.columns
            )

        return pd.DataFrame(valid_rows).reset_index(
            drop=True
        )

    # =========================================================
    # GET VALID PAYMENT OPTIONS
    # =========================================================

    def get_valid_payment_options(self):
        """
        Complete filtering pipeline:

        1. Get options
        2. Check user's accepted methods
        3. Check installment duration
        """

        options = self.get_payment_options()

        options = self.filter_allowed_methods(
            options
        )

        options = self.filter_valid_installments(
            options
        )

        return options

    # =========================================================
    # DISPLAY PAYMENT OPTIONS
    # =========================================================

    def print_options(self, options, title):
        """
        Print payment options in a readable format.
        """

        print("\n" + "=" * 70)

        print(title)

        print("=" * 70)

        if options.empty:

            print("No valid payment options found.")

            return

        for _, row in options.iterrows():

            print(
                f"\nOption ID       : "
                f"{row.get('payment_option_id', 'N/A')}"
            )

            print(
                f"Payment Method  : "
                f"{row.get('payment_method', 'N/A')}"
            )

            print(
                f"Payment Amount  : "
                f"{self._format_number(row.get('payment_amount'))}"
            )

            print(
                f"Number Payments : "
                f"{self._format_number(row.get('number_of_payments'))}"
            )

            print(
                f"First Payment   : "
                f"{row.get('first_payment_date', 'N/A')}"
            )

            print(
                f"Frequency Days  : "
                f"{self._format_number(row.get('payment_frequency_days'))}"
            )

            print(
                f"Financing Fee   : "
                f"{self._format_number(row.get('financing_fee'))}"
            )

            print(
                f"Total Payable   : "
                f"{self._format_number(row.get('total_payable_amount'))}"
            )

    # =========================================================
    # NUMBER FORMATTING
    # =========================================================

    def _format_number(self, value):

        number = self._to_float(value)

        if number is None:
            return "N/A"

        return f"{number:,.2f}"

    # =========================================================
    # OPTION SUMMARY
    # =========================================================

    def get_option_summary(self, row):
        """
        Convert one payment-option row into a clean dictionary.

        This will be useful later when we connect the planner
        to the CashFlowSimulator and Decision Engine.
        """

        return {

            "payment_option_id":
                row.get("payment_option_id"),

            "payment_method":
                str(
                    row.get(
                        "payment_method",
                        ""
                    )
                ).lower(),

            "payment_amount":
                self._to_float(
                    row.get("payment_amount")
                ),

            "number_of_payments":
                self._to_float(
                    row.get("number_of_payments")
                ),

            "first_payment_date":
                row.get(
                    "first_payment_date"
                ),

            "payment_frequency_days":
                self._to_float(
                    row.get(
                        "payment_frequency_days"
                    )
                ),

            "financing_fee":
                self._to_float(
                    row.get(
                        "financing_fee"
                    )
                ),

            "total_payable_amount":
                self._to_float(
                    row.get(
                        "total_payable_amount"
                    )
                )
        }

    # =========================================================
    # GENERATE PAYMENT DATES
    # =========================================================

    def generate_payment_dates(self, row):
        """
        Generate the dates on which payments will occur
        for a selected payment option.
        """

        first_date = pd.to_datetime(
            row.get("first_payment_date"),
            errors="coerce"
        )

        if pd.isna(first_date):
            return []

        number_of_payments = self._to_float(
            row.get("number_of_payments")
        )

        if number_of_payments is None:
            return []

        number_of_payments = int(number_of_payments)

        frequency_days = self._to_float(
            row.get("payment_frequency_days")
        )

        # Full payment or one-time payment
        if number_of_payments == 1:
            return [first_date.date()]

        # Installment option without a valid frequency
        if frequency_days is None or frequency_days <= 0:
            return []

        payment_dates = []

        for payment_number in range(number_of_payments):

            payment_date = (
                first_date
                + pd.Timedelta(
                    days=payment_number * frequency_days
                )
            )

            payment_dates.append(
                payment_date.date()
            )

        return payment_dates


# =============================================================
# TESTING
# =============================================================

if __name__ == "__main__":

    from data_loader import FinancialDataLoader

    request_id = "request_26"

    print("\nLoading request:", request_id)

    # ---------------------------------------------------------
    # Load dataset
    # ---------------------------------------------------------

    loader = FinancialDataLoader()

    context = loader.build_request_context(
        request_id
    )

    if context is None:

        print(
            "ERROR: Request context not found."
        )

        sys.exit(1)

    # ---------------------------------------------------------
    # Create planner
    # ---------------------------------------------------------

    planner = PaymentPlanner(
        context=context,
        simulator=None
    )

    # ---------------------------------------------------------
    # Get payment options
    # ---------------------------------------------------------

    options = planner.get_payment_options()

    print(
        "\nPAYMENT OPTION COLUMNS:"
    )

    print(
        list(options.columns)
    )

    # ---------------------------------------------------------
    # Display first option
    # ---------------------------------------------------------

    if not options.empty:

        print(
            "\nFIRST PAYMENT OPTION:"
        )

        print(
            options.iloc[0].to_dict()
        )

    # ---------------------------------------------------------
    # ALL OPTIONS
    # ---------------------------------------------------------

    planner.print_options(
        options,
        "ALL PAYMENT OPTIONS"
    )

    # ---------------------------------------------------------
    # USER-ALLOWED OPTIONS
    # ---------------------------------------------------------

    allowed_options = (
        planner.filter_allowed_methods(
            options
        )
    )

    planner.print_options(
        allowed_options,
        "OPTIONS ALLOWED BY USER"
    )

    # ---------------------------------------------------------
    # FINAL VALID OPTIONS
    # ---------------------------------------------------------

    valid_options = (
        planner.filter_valid_installments(
            allowed_options
        )
    )
    
    print(
        "\n" + "=" * 70
    )

    print(
        "GENERATED PAYMENT DATES"
    )

    print(
        "=" * 70
    )

    for _, row in valid_options.iterrows():

        dates = planner.generate_payment_dates(row)

        print(
            f"\nOption: {row['payment_option_id']}"
        )

        print(
            f"Payment dates: {dates}"
        )

    planner.print_options(
        valid_options,
        "FINAL VALID PAYMENT OPTIONS"
    )

    # ---------------------------------------------------------
    # OPTION SUMMARIES
    # ---------------------------------------------------------

    print(
        "\n" + "=" * 70
    )

    print(
        "STRUCTURED OPTION SUMMARIES"
    )

    print(
        "=" * 70
    )

    for _, row in valid_options.iterrows():

        summary = planner.get_option_summary(
            row
        )

        print("\n", summary)

    print(
        "\nPAYMENT PLANNER TEST COMPLETE"
    )