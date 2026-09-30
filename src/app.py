import os
import pandas as pd
import streamlit as st
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

# === Step 1: Load environment variables ===
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

# === Streamlit UI ===
st.title("📊 LLM-Based Customer Data Validator")
st.write("Upload an Excel/CSV file to validate customer data using LLM")

uploaded_file = st.file_uploader("Upload your customer data file", type=["xlsx", "csv"])

# === Step 2: Cache LLM Initialization ===
@st.cache_resource
def load_llm():
    """Load and cache the LLM instance for consistent behavior."""
    return ChatGroq(temperature=0, model_name="openai/gpt-oss-120b")

llm = load_llm()

# === Step 3: Define Validation Function ===
template = """
You are a strict data quality validator. 
Your ONLY task is to return a **single output label** (or comma-separated list) — nothing else. 
Never include explanations, reasoning, or additional sentences. 

Validation Rules:
1. **Last Name Rule**
   - Valid if it includes at least one alphabetic character (A–Z or a–z).
   - Do NOT infer meaning; if a field is present, treat it as filled.
   - Can include hyphens (-), dots (.), or apostrophes (').
   - Invalid (LAST_NAME_BLANK) if empty, only spaces, or no letters (e.g., just symbols or numbers).
   - Valid examples: Smith, Txnrxn-Tclx, LNBV, Mc.Donald, X, Jean-Paul
   - Invalid examples: "", " ", "-", "--.--", "123", "_", "#$@"

2. **Mobile Number Rule**
   - Must contain exactly 11 numeric digits (0–9 only).
   - Can start with any digit.
   - Examples:
     - Valid: 34456678890
     - Invalid: 3445667889 (10 digits), 344566788900 (12 digits), abc456678890

3. **Email Rule**
   - Must be a valid email format containing '@' and a domain name.
   - Examples:
     - Valid: john.doe@gmail.com
     - Invalid: john@abc, lochan.123

Output Rules:
- Output ONLY one of the following:
  - VALID
  - LAST_NAME_BLANK
  - INVALID_MOBILE_NUMBER
  - INVALID_EMAIL_FORMAT
  - Or a comma-separated combination of those (e.g., LAST_NAME_BLANK, INVALID_EMAIL_FORMAT)
- Do NOT include sentences, explanations, reasoning, or any other words.

Examples:
Input:
  First Name: Jack
  Last Name: More
  Mobile Number: 34456678890
  Email: jack.more@gmail.com
Output:
  VALID

Input:
  First Name: John
  Last Name: 
  Mobile Number: 3445667889
  Email: john@abc
Output:
  LAST_NAME_BLANK, INVALID_MOBILE_NUMBER, INVALID_EMAIL_FORMAT

Now process this customer Data:
First Name: {First_Name}
Last Name: {Last_Name}
Mobile Number: {Mobile_Number}
Email: {Email_ID}

Return only the final output, no explanations.
"""

def clean_mobile(x):
    """Ensure numeric string without decimals, spaces, or scientific notation."""
    try:
        num = str(int(float(x))).strip()
        num = num.lstrip('+').lstrip('0')
        return num
    except:
        return ""

def validate_row(first_name, last_name, mobile, email):
    """Isolated LLM call for each row to prevent context leakage."""
    local_prompt = PromptTemplate.from_template(template)
    local_chain = local_prompt | llm | (lambda output: output.content.strip())
    return local_chain.invoke({
        "First_Name": first_name,
        "Last_Name": last_name,
        "Mobile_Number": mobile,
        "Email_ID": email
    })

# === Step 4: Processing Logic ===
if uploaded_file is not None:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    df = pd.read_excel(uploaded_file) if file_ext == "xlsx" else pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()

    st.write("### Preview of Uploaded Data:")
    st.dataframe(df.head(5))

    if st.button("🚀 Generate Exceptions"):
        start_time = time.time()
        st.info("Processing started... please wait, this might take some time depending on file size.")

        # Normalize columns
        features = ["First_Name", "Last_Name", "Mobile_Number", "Email_ID"]
        for col in features:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()
        if "Mobile_Number" in df.columns:
            df["Mobile_Number"] = df["Mobile_Number"].apply(clean_mobile)

        # Process rows with progress bar
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        start_time = time.time()

        for idx, row in df.iterrows():
            try:
                exception = validate_row(row["First_Name"], 
                                       row["Last_Name"], 
                                       row["Mobile_Number"], 
                                       row["Email_ID"])
            except Exception as e:
                exception = f"LLM_ERROR: {e}"
            results.append(exception)
            #if idx % 10 == 0:
            progress = (idx + 1)/ len(df)
            progress_bar.progress(int((idx + 1) / len(df)*100))
                # Calculate elapsed time and estimate remaining time
            elapsed = time.time() - start_time
            if idx > 0:
                avg_time_per_row = elapsed / idx
                remaining = avg_time_per_row * (len(df) - idx)
            else:
                remaining = 0
            minutes_left, seconds_left = divmod(int(remaining), 60)
            status_text.text(f"Processing row {idx+1}/{len(df)}"
                                f"({progress*100:.1f}%) - "
                                f"Approx. time left: {minutes_left:02d}:{seconds_left:02d}")
        # Ensure 100% progress bar
        progress_bar.progress(100)

        # Add results to data frame
        df["EXCEPTION"] = results

        end_time = time.time()
        total_time = end_time - start_time
        minutes, seconds = divmod(total_time, 60)

        # Save output
        output_path = r"output\customer_details_llm_groq_validated_streamlit.xlsx"
        df.to_excel(output_path, index=False)

        st.success(f"✅ Processing Completed in {int(minutes)} min {int(seconds)} sec for {len(df)} rows.")
        st.write("### Sample Output:")
        st.dataframe(df.head(10))

        with open(output_path, "rb") as f:
            st.download_button("📥 Download Validated File", f, file_name=output_path)

else:
    st.warning("Please upload a file to begin validation.")
