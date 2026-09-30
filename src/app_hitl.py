import os
import time
from io import BytesIO

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate


# ============================================================
# Step 1: Page configuration and environment variables
# ============================================================

st.set_page_config(
    page_title="LLM Customer Data Validator",
    page_icon="📊",
    layout="wide"
)

load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    st.error(
        "GROQ_API_KEY was not found. "
        "Add GROQ_API_KEY to the .env file and restart the application."
    )
    st.stop()


# ============================================================
# Step 2: Session-state initialization
# ============================================================

def initialize_session_state():
    """Initialize values that must persist across Streamlit reruns."""

    default_values = {
        "validation_completed": False,
        "approval_status": "NOT_REQUIRED",
        "validated_df": None,
        "valid_df": None,
        "exception_df": None,
        "uploaded_file_name": None,
    }

    for key, value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_validation_state():
    """Clear validation results when a different file is uploaded."""

    st.session_state.validation_completed = False
    st.session_state.approval_status = "NOT_REQUIRED"
    st.session_state.validated_df = None
    st.session_state.valid_df = None
    st.session_state.exception_df = None


initialize_session_state()


# ============================================================
# Step 3: Streamlit user interface
# ============================================================

st.title("📊 LLM-Based Customer Data Validator")
st.write(
    "Upload an Excel or CSV file to validate customer data using "
    "the Groq LLM. Records containing exceptions are routed for "
    "human approval before the output file is generated."
)

uploaded_file = st.file_uploader(
    "Upload your customer data file",
    type=["xlsx", "csv"]
)


# ============================================================
# Step 4: Cache the LLM initialization
# ============================================================

@st.cache_resource
def load_llm():
    """Load and cache the Groq LLM instance."""

    return ChatGroq(
        temperature=0,
        model_name="openai/gpt-oss-120b",
        groq_api_key=groq_api_key
    )


llm = load_llm()


# ============================================================
# Step 5: Validation prompt
# ============================================================

template = """
You are a strict data quality validator.

Your ONLY task is to return a single output label or a
comma-separated list of output labels.

Never include explanations, reasoning, or additional sentences.

Validation Rules:

1. Last Name Rule
   - Valid if it includes at least one alphabetic character.
   - Do not infer meaning.
   - If a field is present, treat it as filled.
   - It can include hyphens, dots, or apostrophes.
   - Invalid if empty, only spaces, or contains no letters.

   Valid examples:
   Smith
   Txnrxn-Tclx
   LNBV
   Mc.Donald
   X
   Jean-Paul

   Invalid examples:
   ""
   " "
   "-"
   "--.--"
   "123"
   "_"
   "#$@"

2. Mobile Number Rule
   - Must contain exactly 11 numeric digits.
   - Must contain digits from 0 to 9 only.
   - Can start with any digit.

   Valid example:
   34456678890

   Invalid examples:
   3445667889
   344566788900
   abc456678890

3. Email Rule
   - Must be a valid email format.
   - Must contain the @ symbol.
   - Must contain a valid domain name.

   Valid example:
   john.doe@gmail.com

   Invalid examples:
   john@abc
   lochan.123

Output Rules:

Return ONLY one of the following:

VALID
LAST_NAME_BLANK
INVALID_MOBILE_NUMBER
INVALID_EMAIL_FORMAT

For multiple exceptions, return a comma-separated combination.

Example:

Input:
First Name: Jack
Last Name: More
Mobile Number: 34456678890
Email: jack.more@gmail.com

Output:
VALID

Example:

Input:
First Name: John
Last Name:
Mobile Number: 3445667889
Email: john@abc

Output:
LAST_NAME_BLANK, INVALID_MOBILE_NUMBER, INVALID_EMAIL_FORMAT

Now process the following customer data:

First Name: {First_Name}
Last Name: {Last_Name}
Mobile Number: {Mobile_Number}
Email: {Email_ID}

Return only the final output.
"""


# Create the chain once instead of recreating it for every row
validation_prompt = PromptTemplate.from_template(template)
validation_chain = (
    validation_prompt
    | llm
    | (lambda output: output.content.strip())
)


# ============================================================
# Step 6: Helper functions
# ============================================================

ALLOWED_EXCEPTION_LABELS = {
    "LAST_NAME_BLANK",
    "INVALID_MOBILE_NUMBER",
    "INVALID_EMAIL_FORMAT",
}


def clean_mobile(value):
    """
    Normalize the mobile number while preserving leading zeroes
    whenever the uploaded value is available as text.
    """

    if pd.isna(value):
        return ""

    mobile = str(value).strip()

    # Convert Excel-style numeric values such as 34456678890.0
    if mobile.endswith(".0") and mobile[:-2].isdigit():
        mobile = mobile[:-2]

    # Remove an optional leading plus sign
    if mobile.startswith("+"):
        mobile = mobile[1:]

    # Remove spaces from the mobile number
    mobile = mobile.replace(" ", "")

    return mobile


def normalize_llm_response(response):
    """
    Normalize and validate the LLM response.

    Unexpected model responses are converted into LLM_ERROR
    rather than being incorrectly treated as valid.
    """

    if not response:
        return "LLM_ERROR: Empty response"

    response = response.strip().upper()

    if response == "VALID":
        return "VALID"

    labels = [
        label.strip()
        for label in response.split(",")
        if label.strip()
    ]

    if labels and all(
        label in ALLOWED_EXCEPTION_LABELS
        for label in labels
    ):
        return ", ".join(labels)

    return f"LLM_ERROR: Unexpected response: {response}"


def validate_row(first_name, last_name, mobile, email):
    """Run a separate LLM validation request for one customer."""

    result = validation_chain.invoke({
        "First_Name": first_name,
        "Last_Name": last_name,
        "Mobile_Number": mobile,
        "Email_ID": email
    })

    return normalize_llm_response(result)


def dataframe_to_excel_bytes(dataframe):
    """Convert a DataFrame into an in-memory Excel file."""

    output_buffer = BytesIO()

    with pd.ExcelWriter(
        output_buffer,
        engine="openpyxl"
    ) as writer:
        dataframe.to_excel(
            writer,
            index=False,
            sheet_name="Validated_Customers"
        )

    output_buffer.seek(0)
    return output_buffer.getvalue()


def load_uploaded_file(file):
    """Load an uploaded Excel or CSV file."""

    extension = file.name.rsplit(".", 1)[-1].lower()

    if extension == "xlsx":
        dataframe = pd.read_excel(
            file,
            dtype={
                "First_Name": str,
                "Last_Name": str,
                "Mobile_Number": str,
                "Email_ID": str
            }
        )
    else:
        dataframe = pd.read_csv(
            file,
            dtype={
                "First_Name": str,
                "Last_Name": str,
                "Mobile_Number": str,
                "Email_ID": str
            }
        )

    dataframe.columns = dataframe.columns.str.strip()
    return dataframe


def validate_required_columns(dataframe):
    """Return any required columns missing from the dataset."""

    required_columns = [
        "First_Name",
        "Last_Name",
        "Mobile_Number",
        "Email_ID"
    ]

    return [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]


def approve_validation():
    """Approve the reviewed validation results."""

    st.session_state.approval_status = "APPROVED"


def reject_validation():
    """Reject the reviewed validation results."""

    st.session_state.approval_status = "REJECTED"


# ============================================================
# Step 7: File processing
# ============================================================

if uploaded_file is None:
    st.warning("Please upload a file to begin validation.")

else:
    # Reset results when the user uploads a different file
    if st.session_state.uploaded_file_name != uploaded_file.name:
        reset_validation_state()
        st.session_state.uploaded_file_name = uploaded_file.name

    try:
        df = load_uploaded_file(uploaded_file)

    except Exception as error:
        st.error(f"Unable to read the uploaded file: {error}")
        st.stop()

    missing_columns = validate_required_columns(df)

    if missing_columns:
        st.error(
            "The uploaded file is missing the following required columns: "
            + ", ".join(missing_columns)
        )
        st.stop()

    st.write("### Preview of Uploaded Data")
    st.dataframe(df.head(5), use_container_width=True)

    st.caption(
        f"Uploaded file: {uploaded_file.name} | "
        f"Total records: {len(df)}"
    )

    if st.button(
        "🚀 Generate Exceptions",
        type="primary",
        disabled=st.session_state.validation_completed
    ):
        if df.empty:
            st.warning("The uploaded file contains no customer records.")
            st.stop()

        processing_df = df.copy()

        features = [
            "First_Name",
            "Last_Name",
            "Mobile_Number",
            "Email_ID"
        ]

        for column in features:
            processing_df[column] = (
                processing_df[column]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        processing_df["Mobile_Number"] = (
            processing_df["Mobile_Number"].apply(clean_mobile)
        )

        results = []
        total_rows = len(processing_df)

        progress_bar = st.progress(0)
        status_text = st.empty()

        start_time = time.time()

        for position, (_, row) in enumerate(
            processing_df.iterrows(),
            start=1
        ):
            try:
                exception = validate_row(
                    row["First_Name"],
                    row["Last_Name"],
                    row["Mobile_Number"],
                    row["Email_ID"]
                )

            except Exception as error:
                exception = f"LLM_ERROR: {error}"

            results.append(exception)

            progress_percentage = int(
                (position / total_rows) * 100
            )
            progress_bar.progress(progress_percentage)

            elapsed_time = time.time() - start_time
            average_time_per_row = elapsed_time / position
            remaining_rows = total_rows - position
            estimated_remaining = (
                average_time_per_row * remaining_rows
            )

            minutes_left, seconds_left = divmod(
                int(estimated_remaining),
                60
            )

            status_text.text(
                f"Processing row {position}/{total_rows} "
                f"({progress_percentage}%) | "
                f"Approximate time left: "
                f"{minutes_left:02d}:{seconds_left:02d}"
            )

        progress_bar.progress(100)
        status_text.text("Validation completed.")

        processing_df["EXCEPTION"] = results

        # Split records into valid and exception datasets
        valid_df = processing_df[
            processing_df["EXCEPTION"] == "VALID"
        ].copy()

        exception_df = processing_df[
            processing_df["EXCEPTION"] != "VALID"
        ].copy()

        # Store results across Streamlit reruns
        st.session_state.validated_df = processing_df
        st.session_state.valid_df = valid_df
        st.session_state.exception_df = exception_df
        st.session_state.validation_completed = True

        if exception_df.empty:
            st.session_state.approval_status = "NOT_REQUIRED"
        else:
            st.session_state.approval_status = "PENDING"

        total_time = time.time() - start_time
        minutes, seconds = divmod(int(total_time), 60)

        st.success(
            f"Validation completed in {minutes} min "
            f"{seconds} sec for {total_rows} records."
        )

        # Force the app to rerun and display the approval section
        st.rerun()


# ============================================================
# Step 8: Human-in-the-loop review and approval
# ============================================================

if (
    st.session_state.validation_completed
    and st.session_state.validated_df is not None
):
    validated_df = st.session_state.validated_df
    valid_df = st.session_state.valid_df
    exception_df = st.session_state.exception_df

    valid_count = len(valid_df)
    exception_count = len(exception_df)
    total_count = len(validated_df)

    st.divider()
    st.write("## Validation Summary")

    metric_col1, metric_col2, metric_col3 = st.columns(3)

    metric_col1.metric(
        label="Total Records",
        value=total_count
    )

    metric_col2.metric(
        label="Valid Records",
        value=valid_count
    )

    metric_col3.metric(
        label="Exception Records",
        value=exception_count
    )

    st.write("### Validation Results")
    st.dataframe(
        validated_df,
        use_container_width=True
    )

    # --------------------------------------------------------
    # Exceptions found: trigger human-in-the-loop
    # --------------------------------------------------------

    if exception_count > 0:
        st.warning(
            f"Human review is required because "
            f"{exception_count} record(s) contain exceptions."
        )

        st.write("### Records Requiring Human Review")
        st.dataframe(
            exception_df,
            use_container_width=True
        )

        approval_status = st.session_state.approval_status

        if approval_status == "PENDING":
            st.info(
                "The workflow is paused. Review the exception "
                "records and approve or reject the validation result."
            )

            approve_col, reject_col = st.columns(2)

            with approve_col:
                st.button(
                    "✅ Approve",
                    type="primary",
                    use_container_width=True,
                    on_click=approve_validation
                )

            with reject_col:
                st.button(
                    "❌ Reject",
                    use_container_width=True,
                    on_click=reject_validation
                )

        elif approval_status == "APPROVED":
            st.success(
                "The validation result has been approved. "
                "The output contains only records marked VALID."
            )

            if valid_df.empty:
                st.warning(
                    "No output file was generated because "
                    "there are no VALID records."
                )
            else:
                output_bytes = dataframe_to_excel_bytes(valid_df)

                st.download_button(
                    label="📥 Download Approved VALID Records",
                    data=output_bytes,
                    file_name=(
                        "customer_details_approved_valid_records.xlsx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    type="primary"
                )

        elif approval_status == "REJECTED":
            st.error(
                "The validation result was rejected. "
                "No output file has been generated."
            )

            if st.button(
                "🔄 Return to Pending Review",
                use_container_width=False
            ):
                st.session_state.approval_status = "PENDING"
                st.rerun()

    # --------------------------------------------------------
    # No exceptions: no human approval required
    # --------------------------------------------------------

    else:
        st.success(
            "All records are VALID. Human approval is not required."
        )

        output_bytes = dataframe_to_excel_bytes(valid_df)

        st.download_button(
            label="📥 Download VALID Records",
            data=output_bytes,
            file_name="customer_details_valid_records.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            type="primary"
        )

    st.divider()

    if st.button("🗑️ Clear Results and Start Again"):
        reset_validation_state()
        st.session_state.uploaded_file_name = None
        st.rerun()