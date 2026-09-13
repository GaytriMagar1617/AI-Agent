import pandas as pd
import numpy as np
from datetime import timedelta
from data_loader import FinancialDataLoader


class ForecastEngine:

    def __init__(self, context):

        self.context = context

        # =====================================================
        # REQUEST
        # =====================================================

        self.request = context.get("request", {})

        # =====================================================
        # USER FINANCIAL PROFILE
        # =====================================================

        self.profile = context.get("user_profile", {})

        # =====================================================
        # FINANCIAL EVENTS
        # =====================================================

        self.events = pd.DataFrame(
            context.get("financial_events", [])
        ).copy()

        # =====================================================
        # REQUEST DATE
        # =====================================================

        request_date_str = self.request.get("request_date")

        if request_date_str:
            self.request_date = pd.to_datetime(
                request_date_str,
                errors="coerce"
            ).date()
        else:
            self.request_date = None

        # =====================================================
        # HOME CURRENCY
        # =====================================================

        self.home_currency = str(
            self.profile.get(
                "home_currency",
                "USD"
            )
        ).upper()

        # =====================================================
        # USER EXPENSE PREFERENCES
        # =====================================================

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

    # =========================================================
    # HELPER: SPLIT PROFILE CATEGORIES
    # =========================================================

    def _split_categories(self, value):

        if value is None:
            return set()

        try:
            if pd.isna(value):
                return set()
        except Exception:
            pass

        return {
            item.strip().lower()
            for item in str(value).split("|")
            if item.strip()
        }

    # =========================================================
    # HELPER: NORMALIZE END DATE
    # =========================================================

    def _normalize_end_date(self, end_date):

        if end_date is None:
            return None

        if isinstance(end_date, pd.Timestamp):
            return end_date.date()

        return pd.to_datetime(
            end_date,
            errors="coerce"
        ).date()

    # =========================================================
    # HELPER: NORMALIZE DIRECTION
    # =========================================================

    def _normalize_direction(self, value):

        if value is None:
            return "unknown"

        value = str(value).strip().lower()

        if value in {
            "debit",
            "expense",
            "outflow",
            "withdrawal"
        }:
            return "debit"

        if value in {
            "credit",
            "income",
            "inflow",
            "deposit"
        }:
            return "credit"

        return value

    # =========================================================
    # GET HISTORICAL EVENTS
    # =========================================================

    def get_historical_events(self):

        df = self.events.copy()

        if df.empty:
            return df

        # -----------------------------------------------------
        # Required columns
        # -----------------------------------------------------

        if "event_date" not in df.columns:
            return pd.DataFrame()

        if "status" not in df.columns:
            return pd.DataFrame()

        # -----------------------------------------------------
        # Convert date
        # -----------------------------------------------------

        df["event_date"] = pd.to_datetime(
            df["event_date"],
            errors="coerce"
        )

        # -----------------------------------------------------
        # Convert status
        # -----------------------------------------------------

        df["status"] = (
            df["status"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.strip()
        )

        # -----------------------------------------------------
        # HISTORICAL = SETTLED ONLY
        # -----------------------------------------------------

        df = df[
            df["event_date"].notna()
        ].copy()

        df = df[
            df["status"] == "settled"
        ].copy()

        # -----------------------------------------------------
        # Only transactions on/before request date
        # -----------------------------------------------------

        if self.request_date:

            df = df[
                df["event_date"].dt.date
                <= self.request_date
            ].copy()

        # -----------------------------------------------------
        # HOME CURRENCY ONLY
        # -----------------------------------------------------

        if "currency" in df.columns:

            df["currency"] = (
                df["currency"]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip()
            )

            df = df[
                df["currency"]
                == self.home_currency
            ].copy()

        # -----------------------------------------------------
        # Make amount numeric
        # -----------------------------------------------------

        if "amount" in df.columns:

            df["amount"] = pd.to_numeric(
                df["amount"],
                errors="coerce"
            )

            df = df[
                df["amount"].notna()
            ].copy()

            df = df[
                df["amount"] >= 0
            ].copy()

        # -----------------------------------------------------
        # Normalize direction
        # -----------------------------------------------------

        if "direction" in df.columns:

            df["direction"] = (
                df["direction"]
                .apply(self._normalize_direction)
            )

        return df

    # =========================================================
    # DETECT RECURRING CATEGORIES
    # =========================================================

    def detect_recurring_categories(self):

        df = self.get_historical_events()

        results = []

        if df.empty:
            return pd.DataFrame()

        if "category" not in df.columns:
            return pd.DataFrame()

        # -----------------------------------------------------
        # Group by category
        # -----------------------------------------------------

        for category, group in df.groupby("category"):

            if pd.isna(category):
                continue

            category = str(category).strip()

            if not category:
                continue

            group = group.sort_values(
                "event_date"
            ).copy()

            # -------------------------------------------------
            # Need enough historical observations
            # -------------------------------------------------

            count = len(group)

            if count < 5:
                continue

            # -------------------------------------------------
            # Calculate transaction intervals
            # -------------------------------------------------

            intervals = (
                group["event_date"]
                .diff()
                .dt.days
                .dropna()
            )

            intervals = intervals[
                intervals > 0
            ]

            if len(intervals) < 3:
                continue

            median_interval = float(
                intervals.median()
            )

            interval_std = float(
                intervals.std()
            )

            if pd.isna(interval_std):
                interval_std = 0.0

            # -------------------------------------------------
            # Pattern detection
            # -------------------------------------------------

            monthly_pattern = (
                20 <= median_interval <= 40
            )

            weekly_pattern = (
                5 <= median_interval <= 10
            )

            if not (
                monthly_pattern
                or
                weekly_pattern
            ):
                continue

            # -------------------------------------------------
            # CONSISTENCY CHECK
            #
            # Avoid treating highly irregular categories
            # as recurring.
            # -------------------------------------------------

            if median_interval > 0:

                relative_variation = (
                    interval_std
                    / median_interval
                )

            else:

                relative_variation = 999

            # Allow some natural variation.
            interval_consistent = (
                relative_variation <= 0.75
            )

            if not interval_consistent:
                continue

            # -------------------------------------------------
            # Determine direction
            # -------------------------------------------------

            if "direction" in group.columns:

                direction_mode = (
                    group["direction"]
                    .dropna()
                    .astype(str)
                    .str.lower()
                    .mode()
                )

                if not direction_mode.empty:

                    direction = (
                        self._normalize_direction(
                            direction_mode.iloc[0]
                        )
                    )

                else:

                    direction = "unknown"

            else:

                direction = "unknown"

            # -------------------------------------------------
            # Determine event type
            # -----------------------------------------------------

            if "event_type" in group.columns:

                event_type_mode = (
                    group["event_type"]
                    .dropna()
                    .astype(str)
                    .mode()
                )

                if not event_type_mode.empty:

                    event_type = str(
                        event_type_mode.iloc[0]
                    )

                else:

                    event_type = "unknown"

            else:

                event_type = "unknown"

            # -------------------------------------------------
            # Amount statistics
            # -------------------------------------------------

            amounts = pd.to_numeric(
                group["amount"],
                errors="coerce"
            ).dropna()

            if amounts.empty:
                continue

            median_amount = float(
                amounts.median()
            )

            mean_amount = float(
                amounts.mean()
            )

            # -------------------------------------------------
            # Store recurring category
            # -------------------------------------------------

            results.append({

                "category": category,

                "count": count,

                "median_interval_days":
                    median_interval,

                "interval_std":
                    interval_std,

                "interval_variation":
                    relative_variation,

                "median_amount":
                    median_amount,

                "mean_amount":
                    mean_amount,

                "direction":
                    direction,

                "event_type":
                    event_type
            })

        if not results:
            return pd.DataFrame()

        return pd.DataFrame(
            results
        )

    # =========================================================
    # DETERMINE CATEGORY IMPORTANCE
    # =========================================================

    def get_category_importance(self, category):

        category_lower = str(
            category
        ).strip().lower()

        # Protected takes highest priority.
        if category_lower in self.protected_categories:

            return "protected"

        # User explicitly says this can be reduced/stopped.
        if (
            category_lower in self.reduce_categories
            or
            category_lower in self.stop_categories
        ):

            return "flexible"

        return "normal"

    # =========================================================
    # DETERMINE CONSERVATIVE AMOUNT
    # =========================================================

    def get_conservative_amount(
        self,
        group,
        importance
    ):

        amounts = pd.to_numeric(
            group["amount"],
            errors="coerce"
        ).dropna()

        if amounts.empty:
            return 0.0

        median_amount = float(
            amounts.median()
        )

        # -----------------------------------------------------
        # PROTECTED / ESSENTIAL EXPENSES
        #
        # Use an upper historical estimate rather than
        # blindly using the median.
        # -----------------------------------------------------

        if importance == "protected":

            upper_amount = float(
                amounts.quantile(0.75)
            )

            amount = max(
                median_amount,
                upper_amount
            )

            return amount

        # -----------------------------------------------------
        # FLEXIBLE EXPENSES
        #
        # We preserve the historical estimate, but the
        # decision engine can identify it as reducible.
        # -----------------------------------------------------

        if importance == "flexible":

            return median_amount

        # -----------------------------------------------------
        # NORMAL EXPENSES
        # -----------------------------------------------------

        upper_amount = float(
            amounts.quantile(0.75)
        )

        # Moderate conservative estimate.
        amount = (
            0.75 * upper_amount
            +
            0.25 * median_amount
        )

        return float(amount)

    # =========================================================
    # FORECAST ONE CATEGORY
    # =========================================================

    def forecast_category(
        self,
        category,
        end_date
    ):

        end_date = self._normalize_end_date(
            end_date
        )

        if end_date is None:
            return []

        df = self.get_historical_events()

        if df.empty:
            return []

        # -----------------------------------------------------
        # Category filtering
        # -----------------------------------------------------

        category_series = (
            df["category"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        group = df[
            category_series
            == str(category).strip().lower()
        ].sort_values(
            "event_date"
        ).copy()

        if group.empty:
            return []

        # -----------------------------------------------------
        # Need sufficient history
        # -----------------------------------------------------

        if len(group) < 5:
            return []

        # -----------------------------------------------------
        # Calculate intervals
        # -----------------------------------------------------

        intervals = (
            group["event_date"]
            .diff()
            .dt.days
            .dropna()
        )

        intervals = intervals[
            intervals > 0
        ]

        if len(intervals) < 3:
            return []

        median_interval = int(
            round(
                intervals.median()
            )
        )

        if median_interval <= 0:
            return []

        # -----------------------------------------------------
        # Valid recurrence pattern
        # -----------------------------------------------------

        valid_pattern = (
            20 <= median_interval <= 40
            or
            5 <= median_interval <= 10
        )

        if not valid_pattern:
            return []

        # -----------------------------------------------------
        # Interval consistency
        # -----------------------------------------------------

        interval_std = float(
            intervals.std()
        )

        if pd.isna(interval_std):
            interval_std = 0.0

        relative_variation = (
            interval_std
            / median_interval
        )

        if relative_variation > 0.75:
            return []

        # -----------------------------------------------------
        # Determine direction
        # -----------------------------------------------------

        if "direction" in group.columns:

            direction_mode = (
                group["direction"]
                .dropna()
                .astype(str)
                .str.lower()
                .mode()
            )

            if direction_mode.empty:
                direction = "unknown"
            else:
                direction = self._normalize_direction(
                    direction_mode.iloc[0]
                )

        else:

            direction = "unknown"

        # -----------------------------------------------------
        # IMPORTANT:
        # Only forecast expenses from historical recurring
        # spending.
        #
        # Future income must come from confirmed evidence
        # such as financial messages/events.
        # -----------------------------------------------------

        if direction != "debit":

            return []

        # -----------------------------------------------------
        # Category importance
        # -----------------------------------------------------

        importance = (
            self.get_category_importance(
                category
            )
        )

        # -----------------------------------------------------
        # If user can STOP the category, do not assume
        # the expense must occur.
        #
        # We still know it historically existed, but for
        # affordability we should not force it into the
        # conservative cash requirement.
        # -----------------------------------------------------

        category_lower = str(
            category
        ).strip().lower()

        if category_lower in self.stop_categories:

            return []

        # -----------------------------------------------------
        # Conservative amount
        # -----------------------------------------------------

        amount = self.get_conservative_amount(
            group,
            importance
        )

        if amount <= 0:
            return []

        # -----------------------------------------------------
        # Last historical transaction
        # -----------------------------------------------------

        last_date = group[
            "event_date"
        ].iloc[-1]

        # -----------------------------------------------------
        # Generate next date
        # -----------------------------------------------------

        next_date = (
            last_date
            +
            timedelta(
                days=median_interval
            )
        )

        # -----------------------------------------------------
        # Never forecast on/before request date
        # -----------------------------------------------------

        if self.request_date:

            while (
                next_date.date()
                <= self.request_date
            ):

                next_date = (
                    next_date
                    +
                    timedelta(
                        days=median_interval
                    )
                )

        # -----------------------------------------------------
        # Generate future transactions
        # -----------------------------------------------------

        forecasts = []

        while (
            next_date.date()
            <= end_date
        ):

            forecasts.append({

                "date":
                    next_date.date(),

                "category":
                    category,

                "amount":
                    float(amount),

                "currency":
                    self.home_currency,

                "direction":
                    "debit",

                "source":
                    "historical_forecast",

                "importance":
                    importance
            })

            next_date = (
                next_date
                +
                timedelta(
                    days=median_interval
                )
            )

        return forecasts

    # =========================================================
    # GENERATE COMPLETE FORECAST
    # =========================================================

    def generate_forecast(
        self,
        end_date
    ):

        end_date = self._normalize_end_date(
            end_date
        )

        if end_date is None:
            return pd.DataFrame()

        # -----------------------------------------------------
        # Don't forecast backwards.
        # -----------------------------------------------------

        if (
            self.request_date
            and
            end_date < self.request_date
        ):

            return pd.DataFrame()

        # -----------------------------------------------------
        # Detect recurring categories
        # -----------------------------------------------------

        recurring = (
            self.detect_recurring_categories()
        )

        if recurring.empty:
            return pd.DataFrame()

        all_forecasts = []

        # -----------------------------------------------------
        # Forecast each recurring category
        # -----------------------------------------------------

        for _, row in recurring.iterrows():

            category = row[
                "category"
            ]

            forecasts = (
                self.forecast_category(
                    category,
                    end_date
                )
            )

            all_forecasts.extend(
                forecasts
            )

        if not all_forecasts:
            return pd.DataFrame()

        # -----------------------------------------------------
        # DataFrame
        # -----------------------------------------------------

        forecast_df = pd.DataFrame(
            all_forecasts
        )

        # -----------------------------------------------------
        # Normalize dates
        # -----------------------------------------------------

        forecast_df["date"] = pd.to_datetime(
            forecast_df["date"],
            errors="coerce"
        ).dt.date

        # -----------------------------------------------------
        # Remove invalid amounts
        # -----------------------------------------------------

        forecast_df["amount"] = pd.to_numeric(
            forecast_df["amount"],
            errors="coerce"
        )

        forecast_df = forecast_df[
            forecast_df["amount"].notna()
        ].copy()

        forecast_df = forecast_df[
            forecast_df["amount"] > 0
        ].copy()

        # -----------------------------------------------------
        # Remove duplicates
        # -----------------------------------------------------

        forecast_df = forecast_df.drop_duplicates(
            subset=[
                "date",
                "category",
                "amount",
                "direction"
            ]
        )

        # -----------------------------------------------------
        # Sort
        # -----------------------------------------------------

        forecast_df = forecast_df.sort_values(
            [
                "date",
                "category"
            ]
        ).reset_index(
            drop=True
        )

        return forecast_df

    # =========================================================
    # CLASSIFY FORECAST
    # =========================================================

    def classify_forecast(
        self,
        forecast_df
    ):

        if forecast_df.empty:
            return forecast_df

        df = forecast_df.copy()

        # -----------------------------------------------------
        # Normalize category
        # -----------------------------------------------------

        df["category_lower"] = (
            df["category"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        # -----------------------------------------------------
        # Default
        # -----------------------------------------------------

        df["importance"] = "normal"

        # -----------------------------------------------------
        # Protected
        # -----------------------------------------------------

        df.loc[
            df["category_lower"].isin(
                self.protected_categories
            ),
            "importance"
        ] = "protected"

        # -----------------------------------------------------
        # Flexible
        # -----------------------------------------------------

        flexible_categories = (
            self.reduce_categories
            |
            self.stop_categories
        )

        df.loc[
            df["category_lower"].isin(
                flexible_categories
            ),
            "importance"
        ] = "flexible"

        return df

    # =========================================================
    # CONSERVATIVE FORECAST
    # =========================================================

    def get_conservative_forecast(
        self,
        end_date
    ):

        forecast = (
            self.generate_forecast(
                end_date
            )
        )

        if forecast.empty:
            return forecast

        return self.classify_forecast(
            forecast
        )


# =============================================================
# TEST PROGRAM
# =============================================================

if __name__ == "__main__":

    print("\n" + "=" * 80)
    print("IMPROVED FORECAST ENGINE TEST")
    print("=" * 80)

    # ---------------------------------------------------------
    # REQUEST TO TEST
    # ---------------------------------------------------------

    request_id = "request_26"

    print(
        f"\nTesting request: {request_id}"
    )

    # ---------------------------------------------------------
    # LOAD DATASET
    # ---------------------------------------------------------

    print("\nLoading financial dataset...")

    loader = FinancialDataLoader()

    # ---------------------------------------------------------
    # BUILD CONTEXT
    # ---------------------------------------------------------

    context = loader.build_request_context(
        request_id
    )

    # ---------------------------------------------------------
    # CREATE ENGINE
    # ---------------------------------------------------------

    engine = ForecastEngine(
        context
    )

    # =========================================================
    # REQUEST INFORMATION
    # =========================================================

    print("\n" + "=" * 80)
    print("REQUEST INFORMATION")
    print("=" * 80)

    print(
        "Request date:",
        engine.request_date
    )

    print(
        "Home currency:",
        engine.home_currency
    )

    # =========================================================
    # USER PREFERENCES
    # =========================================================

    print("\n" + "=" * 80)
    print("USER EXPENSE PREFERENCES")
    print("=" * 80)

    print(
        "Protected:",
        engine.protected_categories
    )

    print(
        "Can reduce:",
        engine.reduce_categories
    )

    print(
        "Can stop:",
        engine.stop_categories
    )

    # =========================================================
    # HISTORICAL EVENTS
    # =========================================================

    historical = (
        engine.get_historical_events()
    )

    print("\n" + "=" * 80)
    print("HISTORICAL EVENTS")
    print("=" * 80)

    print(
        "Historical settled events:",
        len(historical)
    )

    # =========================================================
    # RECURRING CATEGORIES
    # =========================================================

    print("\n" + "=" * 80)
    print("RECURRING CATEGORIES")
    print("=" * 80)

    recurring = (
        engine.detect_recurring_categories()
    )

    if recurring.empty:

        print(
            "No recurring categories detected."
        )

    else:

        columns_to_show = [
            "category",
            "count",
            "median_interval_days",
            "interval_variation",
            "median_amount",
            "direction"
        ]

        available_columns = [
            col
            for col in columns_to_show
            if col in recurring.columns
        ]

        print(
            recurring[
                available_columns
            ].to_string(
                index=False
            )
        )

    # =========================================================
    # DESIRED COMPLETION DATE
    # =========================================================

    desired_date_str = (
        context["request"].get(
            "desired_completion_date"
        )
    )

    if desired_date_str:

        desired_date = pd.to_datetime(
            desired_date_str,
            errors="coerce"
        ).date()

        # -----------------------------------------------------
        # FORECAST
        # -----------------------------------------------------

        print("\n" + "=" * 80)
        print(
            "CONSERVATIVE FORECAST UNTIL "
            "DESIRED COMPLETION DATE"
        )
        print("=" * 80)

        print(
            "Forecast period:",
            engine.request_date,
            "to",
            desired_date
        )

        forecast = (
            engine.get_conservative_forecast(
                desired_date
            )
        )

        if forecast.empty:

            print(
                "\nNo future recurring "
                "expenses forecast."
            )

        else:

            print(
                "\nTotal forecast transactions:",
                len(forecast)
            )

            print()

            display_columns = [
                "date",
                "category",
                "amount",
                "currency",
                "direction",
                "importance"
            ]

            available_columns = [
                col
                for col in display_columns
                if col in forecast.columns
            ]

            print(
                forecast[
                    available_columns
                ].to_string(
                    index=False
                )
            )

            # -------------------------------------------------
            # SUMMARY
            # -------------------------------------------------

            print("\n" + "=" * 80)
            print("FORECAST SUMMARY")
            print("=" * 80)

            direction_series = (
                forecast["direction"]
                .fillna("")
                .astype(str)
                .str.lower()
            )

            debit_total = forecast.loc[
                direction_series == "debit",
                "amount"
            ].sum()

            credit_total = forecast.loc[
                direction_series == "credit",
                "amount"
            ].sum()

            protected_total = forecast.loc[
                forecast["importance"]
                == "protected",
                "amount"
            ].sum()

            flexible_total = forecast.loc[
                forecast["importance"]
                == "flexible",
                "amount"
            ].sum()

            normal_total = forecast.loc[
                forecast["importance"]
                == "normal",
                "amount"
            ].sum()

            print(
                f"Forecast income:     "
                f"{credit_total:,.2f}"
            )

            print(
                f"Forecast expenses:   "
                f"{debit_total:,.2f}"
            )

            print(
                f"Protected expenses:  "
                f"{protected_total:,.2f}"
            )

            print(
                f"Flexible expenses:   "
                f"{flexible_total:,.2f}"
            )

            print(
                f"Normal expenses:     "
                f"{normal_total:,.2f}"
            )

            print("\nForecast completed successfully.")

    else:

        print(
            "\nNo desired completion date "
            "found in request."
        )

    print("\n" + "=" * 80)
    print("IMPROVED FORECAST ENGINE TEST COMPLETE")
    print("=" * 80)