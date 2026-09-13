"""
message_extractor.py

Stage 2B of the Buy or Wait? financial agent.

Purpose:
    Extract financially relevant information from user messages.

The extractor converts unstructured messages into structured
financial evidence that can later be consumed by the
financial engine.

We use deterministic Python parsing first.
An LLM can be added later as a fallback for difficult messages.
"""

import re
from datetime import datetime
import pandas as pd

from data_loader import FinancialDataLoader


class MessageExtractor:

    def __init__(self, messages):
        self.messages = messages

    # ========================================================
    # 1. EXTRACT AMOUNT
    # ========================================================

    def extract_amount(self, text):
        """
        Extract a monetary amount from text.

        Example:

            IDR 30780000

        becomes:

            30780000.0
        """

        if not text:
            return None, None

        # Look for currency followed by number
        pattern = r"\b([A-Z]{3})\s*([\d][\d,]*(?:\.\d+)?)"

        matches = re.findall(pattern, text)

        if not matches:
            return None, None

        currency, amount_text = matches[0]

        amount_text = amount_text.replace(",", "")

        try:
            amount = float(amount_text)
        except ValueError:
            return None, None

        return amount, currency

    # ========================================================
    # 2. EXTRACT DATE
    # ========================================================

    def extract_dates(self, text):
        """
        Extract ISO dates from message text.

        Example:

            2025-08-15

        becomes:

            date(2025, 8, 15)
        """

        if not text:
            return []

        pattern = r"\b\d{4}-\d{2}-\d{2}\b"

        matches = re.findall(pattern, text)

        dates = []

        for value in matches:
            try:
                dates.append(
                    pd.to_datetime(value).date()
                )
            except Exception:
                pass

        return dates

    # ========================================================
    # 3. DETERMINE FINANCIAL TYPE
    # ========================================================

    def determine_type(self, text):
        """
        Determine whether the message describes:

            income
            expense
            unknown

        This is deliberately conservative.
        """

        if not text:
            return "unknown"

        text_lower = text.lower()

        income_keywords = [
            "payment",
            "pembayaran",
            "invoice",
            "paid",
            "received",
            "salary",
            "income",
            "refund",
            "approved",
            "disbursement",
        ]

        expense_keywords = [
            "purchase",
            "payment due",
            "bill",
            "rent",
            "fee",
            "charge",
            "transfer",
        ]

        income_score = sum(
            1
            for word in income_keywords
            if word in text_lower
        )

        expense_score = sum(
            1
            for word in expense_keywords
            if word in text_lower
        )

        if income_score > expense_score:
            return "income"

        if expense_score > income_score:
            return "expense"

        return "unknown"

    # ========================================================
        # ========================================================
    # 4. DETERMINE CONFIRMATION
    # ========================================================

    def determine_confirmation(self, text):
        """
        Determine the status of the financial transaction described
        by the message.

        Important:
        A message may contain both confirmed and pending information.
        We should prioritize the status of the specific transaction
        described by the extracted amount.
        """

        if not text:
            return "unknown"

        text_lower = text.lower()

        # --------------------------------------------------------
        # Explicit cancellation
        # --------------------------------------------------------

        cancelled_keywords = [
            "cancelled",
            "canceled",
            "dibatalkan",
        ]

        if any(
            word in text_lower
            for word in cancelled_keywords
        ):
            return "cancelled"

        # --------------------------------------------------------
        # Explicit confirmation
        # --------------------------------------------------------

        confirmed_phrases = [
            "disetujui pembayaran",
            "sudah dikonfirmasi",
            "pembayaran ... disetujui",
            "approved payment",
            "payment confirmed",
            "confirmed payment",
            "invoice approved",
            "faktur disetujui",
        ]

        if any(
            phrase in text_lower
            for phrase in confirmed_phrases
        ):
            return "confirmed"

        # --------------------------------------------------------
        # English confirmation
        # --------------------------------------------------------

        if (
            "approved" in text_lower
            and "invoice" in text_lower
        ):
            return "confirmed"

        # --------------------------------------------------------
        # Pending
        # --------------------------------------------------------

        pending_phrases = [
            "menunggu persetujuan",
            "masih menunggu",
            "pending approval",
            "awaiting approval",
            "pending",
        ]

        if any(
            phrase in text_lower
            for phrase in pending_phrases
        ):
            return "pending"

        return "unknown"

    # ========================================================
    # 5. EXTRACT ONE MESSAGE
    # ========================================================

    def extract_message(self, message):
        """
        Convert one message into structured financial evidence.
        """

        text = str(
            message.get(
                "message_text",
                ""
            )
        )

        amount, currency = self.extract_amount(text)

        dates = self.extract_dates(text)

        financial_type = self.determine_type(text)

        confirmation = self.determine_confirmation(text)

        return {
            "message_id": message.get(
                "message_id"
            ),

            "user_id": message.get(
                "user_id"
            ),

            "request_id": message.get(
                "request_id"
            ),

            "related_event_id": message.get(
                "related_event_id"
            ),

            "sent_at": message.get(
                "sent_at"
            ),

            "source_type": message.get(
                "source_type"
            ),

            "amount": amount,

            "currency": currency,

            "dates": [
                str(date)
                for date in dates
            ],

            "expected_date": (
                str(dates[0])
                if dates
                else None
            ),

            "financial_type": financial_type,

            "confirmation": confirmation,

            "message_text": text,
        }

    # ========================================================
    # 6. EXTRACT ALL
    # ========================================================

    def extract_all(self):

        extracted = []

        for message in self.messages:

            result = self.extract_message(
                message
            )

            # Keep only messages containing
            # potentially useful financial information.

            if (
                result["amount"] is not None
                or result["financial_type"] != "unknown"
            ):
                extracted.append(result)

        return extracted


# ============================================================
# TEST
# ============================================================

def main():

    print("\n" + "=" * 80)
    print("MESSAGE EXTRACTION TEST")
    print("=" * 80)

    loader = FinancialDataLoader()

    context = loader.build_request_context(
        "request_26"
    )

    messages = context["messages"]

    extractor = MessageExtractor(
        messages
    )

    results = extractor.extract_all()

    print(
        f"\nFinancial messages found: "
        f"{len(results)}"
    )

    for result in results:

        print("\n" + "-" * 80)

        print(
            f"Message ID:       "
            f"{result['message_id']}"
        )

        print(
            f"Amount:           "
            f"{result['amount']}"
        )

        print(
            f"Currency:         "
            f"{result['currency']}"
        )

        print(
            f"Expected date:    "
            f"{result['expected_date']}"
        )

        print(
            f"Financial type:   "
            f"{result['financial_type']}"
        )

        print(
            f"Confirmation:     "
            f"{result['confirmation']}"
        )

        print(
            f"Message:          "
            f"{result['message_text']}"
        )


if __name__ == "__main__":
    main()