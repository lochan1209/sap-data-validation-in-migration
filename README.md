# 📊 LLM-Based Customer Data Validator

A Streamlit application that validates customer records from Excel or CSV files using a Groq-hosted Large Language Model through LangChain.

The application checks customer last names, mobile numbers, and email addresses, then assigns an exception label to each record. Once processing is complete, users can preview and download the validated dataset as an Excel file.

## Features

- Upload customer data in `.xlsx` or `.csv` format
- Preview uploaded records before processing
- Validate every customer record independently using an LLM
- Display row-level processing progress
- Show an approximate remaining processing time
- Generate standardized data-quality exception labels
- Export validated records to Excel
- Download the validated file directly from the Streamlit interface
- Cache the LLM instance to avoid unnecessary reinitialization
- Capture row-level LLM errors without stopping the entire process

## Technology Stack

- Python
- Streamlit
- Pandas
- LangChain
- LangChain Groq integration
- Groq API
- python-dotenv
- OpenPyXL

## Project Structure

```text
customer-data-validator/
├── src/app.py
├── .env
├── requirements.txt
├── output/
│   └── customer_details_llm_groq_validated_streamlit.xlsx
└── README.md

## Prerequisites

Before running the application, ensure that you have:

Python 3.10 or later
A valid Groq API key
Internet connectivity for LLM requests
A customer dataset in Excel or CSV format

## Installation
1. Clone or download the project
git clone <repository-url>
cd customer-data-validator

2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

3. Install the required packages

Create a requirements.txt file with the following content:
streamlit
pandas
python-dotenv
langchain-core
langchain-groq
openpyxl

Install the dependencies:
pip install -r requirements.txt

## Environment Configuration

Create a .env file in the project root directory:
GROQ_API_KEY=your_groq_api_key_here
Replace your_groq_api_key_here with your actual Groq API key.

For security, do not commit the .env file to source control.

Add the following entries to .gitignore:
.env
.venv/
__pycache__/
output/
*.py*

## Input File Requirements

The uploaded Excel or CSV file must contain the following columns:

Column	Description	Example

| First_Name | Customer's first name | Jack | | Last_Name | Customer's last name | More | | Mobile_Number | Customer's mobile number | 34456678890 | | Email_ID | Customer's email address | jack.more@gmail.com |

## Exception Labels

The application generates one of the following values in the EXCEPTION column:
VALID
LAST_NAME_BLANK
INVALID_MOBILE_NUMBER
INVALID_EMAIL_FORMAT

If a record violates multiple rules, the labels are returned as a comma-separated combination.
LAST_NAME_BLANK, INVALID_MOBILE_NUMBER, INVALID_EMAIL_FORMAT

## Running the Application
streamlit run app.py
Streamlit will display the application URL in the terminal. Open that URL in a browser if it does not open automatically.

## How to Use
Open the Streamlit application.
Upload an Excel or CSV customer data file.
Review the preview of the first five rows.
Select Generate Exceptions.
Monitor the progress bar and processing status.
Review the sample validated output.
Select Download Validated File to download the Excel result.
Processing Workflow

The application performs the following steps:

Loads the Groq API key from the .env file.
Initializes and caches the LLM.
Accepts an Excel or CSV file through the Streamlit interface.
Removes leading and trailing spaces from column names.
Normalizes the required customer fields.
Cleans the mobile number value.
Sends each customer record to the LLM independently.
Captures the validation result for each row.
Adds the result to a new EXCEPTION column.
Saves the validated dataset as an Excel file.
Makes the generated file available for download.

Each row is processed using an isolated LangChain prompt invocation to reduce the possibility of context leaking between customer records.

## Output File

The validated dataset is saved as:
output/customer_details_llm_groq_vali*ated_streamlit.xlsx

## Error Handling

If an LLM request fails for a particular row, processing continues for the remaining records.

The affected record receives a value similar to:
LLM_ERROR: <error details>

This ensures that one failed request does not stop validation of the complete dataset.

