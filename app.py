import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="PRO GST Excel Reconciliation", layout="wide")

st.title("🚀 PRO GST Purchase vs GSTR-2B")

# ======================================
# ⭐ STICKY CHART STYLE (chart won't move while scrolling)
# ======================================
st.markdown("""
<style>
.sticky-chart {
    position: sticky;
    top: 70px;
    z-index: 999;
    background-color: white;
    padding-top: 10px;
}
</style>
""", unsafe_allow_html=True)

# ======================================
# GSTIN VALIDATION FUNCTION
# ======================================
def valid_gstin(gstin):
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    return bool(re.match(pattern, str(gstin)))

# ======================================
# FILE UPLOADS
# ======================================
purchase_file = st.file_uploader("Upload Purchase Register Excel", type=["xlsx"])
b2b_file = st.file_uploader("Upload GSTR-2B Excel", type=["xlsx"])

if purchase_file and b2b_file:

    # ======================================
    # READ PURCHASE REGISTER
    # ======================================
    purchase_df = pd.read_excel(purchase_file)
    purchase_df.columns = purchase_df.columns.str.strip()

    purchase_df = purchase_df.rename(columns={
        "GSTIN": "GSTIN",
        "Invoice Number": "Invoice_Number",
        "Invoice No": "Invoice_Number",
        "Invoice Date": "Invoice_Date",
        "Invoice_Date": "Invoice_Date",
        "CGST": "CGST",
        "SGST": "SGST",
        "IGST": "IGST"
    })

    if "Invoice_Date" in purchase_df.columns:
        purchase_df["Invoice_Date"] = pd.to_datetime(
            purchase_df["Invoice_Date"], errors='coerce'
        )
    else:
        st.error("❌ Invoice Date column not found in Purchase Excel")
        st.stop()

    # ======================================
    # READ GSTR-2B EXCEL
    # ======================================
    b2b_df = pd.read_excel(b2b_file)
    b2b_df.columns = b2b_df.columns.str.strip()

    b2b_df = b2b_df.rename(columns={
        "GSTIN": "GSTIN",
        "Invoice Number": "Invoice_Number",
        "Invoice No": "Invoice_Number",
        "Invoice Date": "Invoice_Date",
        "Invoice_Date": "Invoice_Date",
        "CGST": "CGST",
        "SGST": "SGST",
        "IGST": "IGST"
    })

    if "Invoice_Date" in b2b_df.columns:
        b2b_df["Invoice_Date"] = pd.to_datetime(
            b2b_df["Invoice_Date"], errors='coerce'
        )
    else:
        st.error("❌ Invoice Date column not found in GSTR-2B Excel")
        st.stop()

    # ======================================
    # FILL EMPTY TAX VALUES
    # ======================================
    for col in ["CGST", "SGST", "IGST"]:
        purchase_df[col] = purchase_df[col].fillna(0)
        b2b_df[col] = b2b_df[col].fillna(0)

    # ======================================
    # GSTIN VALIDATION
    # ======================================
    purchase_df["GSTIN_Valid"] = purchase_df["GSTIN"].apply(valid_gstin)

    # ======================================
    # CREATE UNIQUE KEY
    # ======================================
    purchase_df["KEY"] = (
        purchase_df["GSTIN"].astype(str) + "_" +
        purchase_df["Invoice_Number"].astype(str)
    )

    b2b_df["KEY"] = (
        b2b_df["GSTIN"].astype(str) + "_" +
        b2b_df["Invoice_Number"].astype(str)
    )

    # FAST LOOKUP DICTIONARY
    b2b_dict = b2b_df.set_index("KEY").to_dict("index")

    # ======================================
    # MATCHING ENGINE
    # ======================================
    results = []

    for i, row in purchase_df.iterrows():

        key = row["KEY"]
        status = "Matched"
        remark = ""

        if not row["GSTIN_Valid"]:
            status = "Invalid GSTIN"

        elif key not in b2b_dict:
            status = "Missing in 2B"
            remark = "Invoice not available in GSTR-2B"

        else:
            b2b_row = b2b_dict[key]

            tax_diff = (
                abs(row["CGST"] - b2b_row["CGST"]) +
                abs(row["SGST"] - b2b_row["SGST"]) +
                abs(row["IGST"] - b2b_row["IGST"])
            )

            if tax_diff != 0:
                status = "Mismatch"
                remark = f"Tax Difference = {tax_diff}"

        results.append({
            "GSTIN": row["GSTIN"],
            "Invoice Number": row["Invoice_Number"],
            "Invoice Date": row["Invoice_Date"],
            "CGST": row["CGST"],
            "SGST": row["SGST"],
            "IGST": row["IGST"],
            "Status": status,
            "Remark": remark
        })

    result_df = pd.DataFrame(results)

    # ======================================
    # DASHBOARD
    # ======================================
    st.subheader("📊 PRO Dashboard")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Invoices", len(result_df))
    c2.metric("Matched", len(result_df[result_df["Status"] == "Matched"]))
    c3.metric("Missing", len(result_df[result_df["Status"] == "Missing in 2B"]))
    c4.metric("Mismatch", len(result_df[result_df["Status"] == "Mismatch"]))

    # ======================================
    # ⭐ STICKY STATUS CHART
    # ======================================
    st.subheader("📉 Status Distribution")

    st.markdown('<div class="sticky-chart">', unsafe_allow_html=True)
    st.bar_chart(result_df["Status"].value_counts(), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ======================================
    # VENDOR SUMMARY
    # ======================================
    st.subheader("📈 Vendor Summary")

    vendor_summary = (
        result_df.groupby("GSTIN")["Status"]
        .value_counts()
        .unstack()
        .fillna(0)
    )

    st.dataframe(vendor_summary, use_container_width=True)

    # ======================================
    # RESULT TABLE
    # ======================================
    st.subheader("📄 Detailed Results")
    st.dataframe(result_df, use_container_width=True)

    # ======================================
    # DOWNLOAD REPORT
    # ======================================
    output_file = "PRO_GST_Reconciliation.xlsx"
    result_df.to_excel(output_file, index=False)

    with open(output_file, "rb") as f:
        st.download_button("⬇ Download Report", f, file_name=output_file)
