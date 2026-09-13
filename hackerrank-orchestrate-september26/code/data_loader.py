"""
data_loader.py

Purpose:
    Load the Buy or Wait? contest dataset and retrieve all
    information related to a particular financial request.

This is the DATA RETRIEVAL layer of our AI financial agent.

It does NOT make financial decisions yet.
"""

from pathlib import Path
import pandas as pd
import json
import sys


# ============================================================
# 1. FIND PROJECT AND DATASET DIRECTORIES
# ============================================================

# data_loader.py is inside:
# project/code/data_loader.py
#
# Therefore:
# parent of code = project
# project / dataset = dataset folder

CODE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CODE_DIR.parent
DATASET_DIR = PROJECT_DIR / "dataset"
MEDIA_DIR = DATASET_DIR / "media"
IMAGE_DIR = MEDIA_DIR / "images"


# ============================================================
# 2. CSV FILE PATHS
# ============================================================

REQUESTS_FILE = DATASET_DIR / "requests.csv"
PROFILES_FILE = DATASET_DIR / "financial_profiles.csv"
EVENTS_FILE = DATASET_DIR / "financial_events.csv"
MESSAGES_FILE = DATASET_DIR / "messages.csv"
IMAGES_FILE = DATASET_DIR / "images.csv"
PAYMENT_OPTIONS_FILE = DATASET_DIR / "request_payment_options.csv"
EXCHANGE_RATES_FILE = DATASET_DIR / "exchange_rates.csv"


# ============================================================
# 3. HELPER FUNCTION TO LOAD CSV
# ============================================================

def load_csv(file_path):
    """
    Load a CSV file safely.

    Parameters:
        file_path: Path to CSV file

    Returns:
        pandas DataFrame
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"\nCSV file not found:\n{file_path}\n"
            f"Please check your dataset folder."
        )

    try:
        df = pd.read_csv(file_path)

        # Remove accidental spaces from column names
        df.columns = df.columns.str.strip()

        return df

    except Exception as e:
        raise RuntimeError(
            f"Could not read {file_path.name}: {e}"
        )


# ============================================================
# 4. FINANCIAL DATA LOADER CLASS
# ============================================================

class FinancialDataLoader:

    def __init__(self):
        """
        Load all contest datasets into memory.
        """

        print("\n" + "=" * 70)
        print("LOADING FINANCIAL DATASET")
        print("=" * 70)

        self.requests = load_csv(REQUESTS_FILE)
        self.profiles = load_csv(PROFILES_FILE)
        self.events = load_csv(EVENTS_FILE)
        self.messages = load_csv(MESSAGES_FILE)
        self.images = load_csv(IMAGES_FILE)
        self.payment_options = load_csv(PAYMENT_OPTIONS_FILE)
        self.exchange_rates = load_csv(EXCHANGE_RATES_FILE)

        print(f"Requests loaded:          {len(self.requests)}")
        print(f"Financial profiles:       {len(self.profiles)}")
        print(f"Financial events:         {len(self.events)}")
        print(f"Messages:                 {len(self.messages)}")
        print(f"Images metadata:          {len(self.images)}")
        print(f"Payment options:          {len(self.payment_options)}")
        print(f"Exchange rates:           {len(self.exchange_rates)}")

        print("=" * 70)
        print("DATASET LOADED SUCCESSFULLY")
        print("=" * 70)


    # ========================================================
    # 5. GET ONE REQUEST
    # ========================================================

    def get_request(self, request_id):
        """
        Find a specific request.

        Example:
            get_request("request_26")
        """

        result = self.requests[
            self.requests["request_id"].astype(str) == str(request_id)
        ]

        if result.empty:
            return None

        return result.iloc[0].to_dict()


    # ========================================================
    # 6. GET USER PROFILE
    # ========================================================

    def get_user_profile(self, user_id):
        """
        Find financial profile of a user.
        """

        result = self.profiles[
            self.profiles["user_id"].astype(str) == str(user_id)
        ]

        if result.empty:
            return None

        return result.iloc[0].to_dict()


    # ========================================================
    # 7. GET FINANCIAL EVENTS
    # ========================================================

    def get_user_events(self, user_id):
        """
        Get all financial events belonging to a user.
        """

        result = self.events[
            self.events["user_id"].astype(str) == str(user_id)
        ].copy()

        # Sort by date if event_date exists
        if "event_date" in result.columns:
            result["event_date"] = pd.to_datetime(
                result["event_date"],
                errors="coerce"
            )

            result = result.sort_values("event_date")

        return result.to_dict(orient="records")


    # ========================================================
    # 8. GET USER MESSAGES
    # ========================================================

    def get_user_messages(self, user_id):
        """
        Get all messages belonging to a user.

        The exact dataset schema may contain additional columns,
        so we simply filter using user_id.
        """

        if "user_id" not in self.messages.columns:
            return []

        result = self.messages[
            self.messages["user_id"].astype(str) == str(user_id)
        ]

        return result.to_dict(orient="records")


    # ========================================================
    # 9. GET REQUEST IMAGES
    # ========================================================

    def get_request_images(self, request_id, user_id=None):
        """
        Find image metadata related to a request.

        Some images may be associated directly with request_id,
        while others may be associated with the user's data.
        """

        result = pd.DataFrame()

        # First priority: request_id
        if "request_id" in self.images.columns:

            result = self.images[
                self.images["request_id"].astype(str) == str(request_id)
            ].copy()

        # If nothing was found, try user_id
        if result.empty and user_id is not None:

            if "user_id" in self.images.columns:

                result = self.images[
                    self.images["user_id"].astype(str) == str(user_id)
                ].copy()

        records = result.to_dict(orient="records")

        # Add actual image path when possible
        for record in records:

            image_name = None

            # Try common possible column names
            for column in [
                "image_file",
                "image_filename",
                "filename",
                "file_name",
                "image_path",
                "image_id"
            ]:

                if column in record and pd.notna(record[column]):
                    image_name = str(record[column])
                    break

            if image_name:

                # If the value is already a path
                possible_path = Path(image_name)

                if possible_path.exists():
                    record["local_image_path"] = str(
                        possible_path.resolve()
                    )

                else:
                    # Try inside dataset/media/images
                    image_path = IMAGE_DIR / image_name

                    if image_path.exists():
                        record["local_image_path"] = str(
                            image_path.resolve()
                        )

                    else:
                        record["local_image_path"] = None

        return records


    # ========================================================
    # 10. GET PAYMENT OPTIONS
    # ========================================================

    def get_payment_options(self, request_id):
        """
        Get all payment options available for a request.
        """

        if "request_id" not in self.payment_options.columns:
            return []

        result = self.payment_options[
            self.payment_options["request_id"].astype(str)
            == str(request_id)
        ]

        return result.to_dict(orient="records")


    # ========================================================
    # 11. GET EXCHANGE RATES
    # ========================================================

    def get_exchange_rates(self):
        """
        Return exchange-rate data.

        We will use this later for currency conversion.
        """

        return self.exchange_rates.to_dict(orient="records")


    # ========================================================
    # 12. BUILD COMPLETE REQUEST CONTEXT
    # ========================================================

    def build_request_context(self, request_id):
        """
        Build all information required by the financial agent
        for a single request.

        This is the most important method in this file.

        request_id
            ↓
        request
            ↓
        user_id
            ↓
        profile
        events
        messages
        images
        payment options
        """

        request = self.get_request(request_id)

        if request is None:
            raise ValueError(
                f"Request '{request_id}' was not found."
            )

        user_id = request["user_id"]

        context = {
            "request": request,

            "user_profile": self.get_user_profile(user_id),

            "financial_events": self.get_user_events(user_id),

            "messages": self.get_user_messages(user_id),

            "images": self.get_request_images(
                request_id,
                user_id
            ),

            "payment_options": self.get_payment_options(
                request_id
            ),

            "exchange_rates": self.get_exchange_rates()
        }

        return context


# ============================================================
# 13. PRINT REQUEST CONTEXT
# ============================================================

def print_request_context(context):
    """
    Print the retrieved information in a readable format.
    """

    request = context["request"]

    print("\n")
    print("=" * 80)
    print("REQUEST INFORMATION")
    print("=" * 80)

    print(f"Request ID:              {request.get('request_id')}")
    print(f"User ID:                 {request.get('user_id')}")
    print(f"Request Date:            {request.get('request_date')}")
    print(f"Request Type:            {request.get('request_type')}")
    print(f"Requested Amount:        {request.get('requested_amount')}")
    print(
        f"Desired Completion:     "
        f"{request.get('desired_completion_date')}"
    )
    print(
        f"Partial Payment Allowed:"
        f" {request.get('allows_partial_payment')}"
    )

    print("\nUser Request:")
    print(request.get("request_text"))

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("USER FINANCIAL PROFILE")
    print("=" * 80)

    profile = context["user_profile"]

    if profile:
        for key, value in profile.items():
            print(f"{key}: {value}")
    else:
        print("No financial profile found.")

    # --------------------------------------------------------
    # EVENTS
    # --------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("FINANCIAL EVENTS")
    print("=" * 80)

    events = context["financial_events"]

    print(f"Total events found: {len(events)}")

    # Show first 20 for readability
    for event in events[:20]:

        print("-" * 70)

        for key, value in event.items():
            print(f"{key}: {value}")

    if len(events) > 20:
        print(
            f"\n... {len(events) - 20} more events "
            f"not displayed ..."
        )

    # --------------------------------------------------------
    # MESSAGES
    # --------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("USER MESSAGES")
    print("=" * 80)

    messages = context["messages"]

    print(f"Total messages found: {len(messages)}")

    for message in messages:

        print("-" * 70)

        for key, value in message.items():
            print(f"{key}: {value}")

    # --------------------------------------------------------
    # IMAGES
    # --------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("RELATED IMAGES")
    print("=" * 80)

    images = context["images"]

    print(f"Total related images: {len(images)}")

    for image in images:

        print("-" * 70)

        for key, value in image.items():
            print(f"{key}: {value}")

    # --------------------------------------------------------
    # PAYMENT OPTIONS
    # --------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("PAYMENT OPTIONS")
    print("=" * 80)

    options = context["payment_options"]

    print(f"Total payment options: {len(options)}")

    for option in options:

        print("-" * 70)

        for key, value in option.items():
            print(f"{key}: {value}")

    print("\n")
    print("=" * 80)
    print("CONTEXT RETRIEVAL COMPLETE")
    print("=" * 80)


# ============================================================
# 14. SAVE CONTEXT TO JSON
# ============================================================

def save_context(context, request_id):
    """
    Save retrieved context to a JSON file.

    This is useful for debugging and later development.
    """

    output_file = CODE_DIR / f"context_{request_id}.json"

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            context,
            file,
            indent=4,
            default=str
        )

    print(
        f"\nContext saved to:\n{output_file}"
    )


# ============================================================
# 15. MAIN PROGRAM
# ============================================================

def main():

    # --------------------------------------------------------
    # Check whether request ID was provided
    # --------------------------------------------------------

    if len(sys.argv) < 2:

        print("\nUsage:")
        print("python data_loader.py <request_id>")
        print("\nExample:")
        print("python data_loader.py request_26")
        print()

        return

    request_id = sys.argv[1]

    # --------------------------------------------------------
    # Load dataset
    # --------------------------------------------------------

    try:

        loader = FinancialDataLoader()

    except Exception as e:

        print("\nERROR WHILE LOADING DATA:")
        print(e)

        return

    # --------------------------------------------------------
    # Build request context
    # --------------------------------------------------------

    try:

        context = loader.build_request_context(
            request_id
        )

    except Exception as e:

        print("\nERROR WHILE BUILDING CONTEXT:")
        print(e)

        return

    # --------------------------------------------------------
    # Display results
    # --------------------------------------------------------

    print_request_context(context)

    # --------------------------------------------------------
    # Save JSON copy for debugging
    # --------------------------------------------------------

    save_context(
        context,
        request_id
    )


# ============================================================
# RUN PROGRAM
# ============================================================

if __name__ == "__main__":
    main()