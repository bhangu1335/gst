import streamlit as st
import pandas as pd
import re

# ======================================
# PAGE CONFIG
# ======================================
st.set_page_config(page_title="GST Reconciliation", layout="wide")

st.title("🚀 GST Reconciliation Dashboard")

# ======================================
# STICKY STYLE
# ======================================
st.markdown("""
<style>
.sticky-chart {
    position: sticky;
    top: 70px;
    z-index: 999;
    background-color: white;
}
</style>
""", unsafe_allow_html=True)

# ======================================
# GSTIN VALIDATION
# ======================================
def valid_gstin(gstin):
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    return bool(re.match(pattern, str(gstin)))

# ======================================
# FILE UPLOAD
# ======================================
purchase_file = st.file_uploader("Upload Purchase Register", type=["xlsx"])
b2b_file = st.file_uploader("Upload GSTR-2B", type=["xlsx"])

# ======================================
# MAIN ENGINE
# ======================================
if purchase_file and b2b_file:

    with st.spinner("⚡ Processing GST Data..."):

        # ---------- READ FILES ----------
        purchase_df = pd.read_excel(purchase_file)
        b2b_df = pd.read_excel(b2b_file)

        purchase_df.columns = purchase_df.columns.str.strip()
        b2b_df.columns = b2b_df.columns.str.strip()

        # ---------- FLEXIBLE RENAME ----------
        rename_map = {
            "Invoice Number":"Invoice_Number",
            "Invoice No":"Invoice_Number",
            "Invoice Date":"Invoice_Date",
            "GSTIN":"GSTIN",
            "CGST":"CGST",
            "SGST":"SGST",
            "IGST":"IGST"
        }

        purchase_df = purchase_df.rename(columns=rename_map)
        b2b_df = b2b_df.rename(columns=rename_map)

        # ---------- VALIDATION ----------
        required_cols = ["GSTIN","Invoice_Number","Invoice_Date","CGST","SGST","IGST"]

        for col in required_cols:
            if col not in purchase_df.columns:
                st.error(f"❌ Missing column in Purchase File: {col}")
                st.stop()
            if col not in b2b_df.columns:
                st.error(f"❌ Missing column in 2B File: {col}")
                st.stop()

        # ---------- DATE ----------
        purchase_df["Invoice_Date"] = pd.to_datetime(purchase_df["Invoice_Date"], errors="coerce")
        b2b_df["Invoice_Date"] = pd.to_datetime(b2b_df["Invoice_Date"], errors="coerce")

        # ---------- CLEAN TAX ----------
        for col in ["CGST","SGST","IGST"]:
            purchase_df[col] = purchase_df[col].fillna(0)
            b2b_df[col] = b2b_df[col].fillna(0)

        # ---------- GSTIN VALID ----------
        purchase_df["GSTIN_Valid"] = purchase_df["GSTIN"].apply(valid_gstin)

        # ---------- UNIQUE KEY ----------
        purchase_df["KEY"] = purchase_df["GSTIN"].astype(str) + "_" + purchase_df["Invoice_Number"].astype(str)
        b2b_df["KEY"] = b2b_df["GSTIN"].astype(str) + "_" + b2b_df["Invoice_Number"].astype(str)

        # ======================================
        # ⭐ VECTORISED MATCH ENGINE (PRODUCTION)
        # ======================================
        merged_df = purchase_df.merge(
            b2b_df[["KEY","CGST","SGST","IGST"]],
            on="KEY",
            how="left",
            suffixes=("","_2B")
        )

        # ======================================
        # ⭐ PRIORITY STATUS ENGINE (FIXED)
        # ======================================
        merged_df["Status"] = "Matched"
        merged_df["Remark"] = ""

        # Tax Difference
        merged_df["Tax_Diff"] = (
            (merged_df["CGST"] - merged_df["CGST_2B"]).abs().fillna(0) +
            (merged_df["SGST"] - merged_df["SGST_2B"]).abs().fillna(0) +
            (merged_df["IGST"] - merged_df["IGST_2B"]).abs().fillna(0)
        )

        # 1️⃣ Invalid GSTIN
        merged_df.loc[~merged_df["GSTIN_Valid"], "Status"] = "Invalid GSTIN"

        # 2️⃣ Missing in 2B
        missing_mask = merged_df["CGST_2B"].isna()
        merged_df.loc[missing_mask & merged_df["GSTIN_Valid"], "Status"] = "Missing in 2B"
        merged_df.loc[missing_mask & merged_df["GSTIN_Valid"], "Remark"] = "Invoice not in 2B"

        # 3️⃣ Mismatch
        mismatch_mask = (merged_df["Tax_Diff"] != 0) & (~missing_mask)
        merged_df.loc[mismatch_mask & merged_df["GSTIN_Valid"], "Status"] = "Mismatch"
        merged_df.loc[mismatch_mask & merged_df["GSTIN_Valid"], "Remark"] = "Tax Difference"

        # FINAL RESULT
        result_df = merged_df[[
            "GSTIN","Invoice_Number","Invoice_Date",
            "CGST","SGST","IGST","Status","Remark"
        ]]

    # ======================================
    # ⭐ SAAS SIDEBAR FILTERS
    # ======================================
    st.sidebar.header("🔎 Filters")

    vendor_filter = st.sidebar.multiselect(
        "Select Vendor GSTIN",
        sorted(result_df["GSTIN"].unique())
    )

    status_filter = st.sidebar.multiselect(
        "Status",
        ["Matched","Mismatch","Missing in 2B","Invalid GSTIN"]
    )

    date_range = st.sidebar.date_input("Invoice Date Range", [])

    filtered_df = result_df.copy()

    if vendor_filter:
        filtered_df = filtered_df[filtered_df["GSTIN"].isin(vendor_filter)]

    if status_filter:
        filtered_df = filtered_df[filtered_df["Status"].isin(status_filter)]

    if len(date_range) == 2:
        filtered_df = filtered_df[
            (filtered_df["Invoice_Date"] >= pd.to_datetime(date_range[0])) &
            (filtered_df["Invoice_Date"] <= pd.to_datetime(date_range[1]))
        ]

    # ======================================
    # KPI CARDS
    # ======================================
    st.subheader("📊 Dashboard KPIs")

    c1,c2,c3,c4 = st.columns(4)

    c1.metric("Total",len(filtered_df))
    c2.metric("Matched",len(filtered_df[filtered_df["Status"]=="Matched"]))
    c3.metric("Missing",len(filtered_df[filtered_df["Status"]=="Missing in 2B"]))
    c4.metric("Mismatch",len(filtered_df[filtered_df["Status"]=="Mismatch"]))

    # ======================================
    # STICKY CHART
    # ======================================
    st.subheader("📉 Status Distribution")

    st.markdown('<div class="sticky-chart">', unsafe_allow_html=True)
    st.bar_chart(filtered_df["Status"].value_counts(), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ======================================
    # VENDOR SUMMARY
    # ======================================
    st.subheader("📈 Vendor Summary")

    vendor_summary = (
        filtered_df.groupby("GSTIN")["Status"]
        .value_counts()
        .unstack()
        .fillna(0)
    )

    st.dataframe(vendor_summary,use_container_width=True)

    # ======================================
    # TABLE
    # ======================================
    st.subheader("📄 Detailed Results")
    st.dataframe(filtered_df,use_container_width=True)

    # ======================================
    # DOWNLOAD REPORT
    # ======================================
    output_file="GST_SaaS_Report.xlsx"
    filtered_df.to_excel(output_file,index=False)

    with open(output_file,"rb") as f:
        st.download_button("⬇ Download Filtered Report",f,file_name=output_file)
