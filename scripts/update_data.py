import os
import json
import requests
import pandas as pd
from datetime import datetime
import io

# World Bank Official Monthly Pink Sheet Historical Excel URL
WB_EXCEL_URL = "https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/related/CMO-Historical-Data-Monthly.xlsx"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "commodities.json")

# Target 8 Commodities Mapping
TARGET_COLS = {
    "GOLD": "gold",
    "ALUMINUM": "aluminium",
    "COPPER": "copper",
    "TIN": "tin",
    "TUNGSTEN": "tungsten",
    "STEEL": "steel",
    "RUBBER": "rubber",
    "SILVER": "silver"
}

def fetch_and_update():
    print(f"[{datetime.utcnow().isoformat()}] Fetching latest World Bank Pink Sheet dataset...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        resp = requests.get(WB_EXCEL_URL, headers=headers, timeout=60)
        resp.raise_for_status()
        excel_data = pd.ExcelFile(io.BytesIO(resp.content))
        
        sheet_name = "Monthly Prices" if "Monthly Prices" in excel_data.sheet_names else excel_data.sheet_names[0]
        raw_df = pd.read_excel(excel_data, sheet_name=sheet_name)
        
        # Locate table header
        header_row_idx = None
        for idx, row in raw_df.iterrows():
            first_val = str(row.iloc[0]).strip().upper()
            if any(k in first_val for k in ["DATE", "YEAR", "1960M01"]):
                header_row_idx = idx
                break
                
        if header_row_idx is None:
            header_row_idx = 4
            
        columns = raw_df.iloc[header_row_idx].tolist()
        columns[0] = "Date"
        clean_df = raw_df.iloc[header_row_idx + 1:].copy()
        clean_df.columns = columns
        clean_df = clean_df.dropna(subset=["Date"])
        
        # Standardize date format (YYYY-MM)
        clean_df["Date"] = clean_df["Date"].astype(str).str.strip().str.replace("M", "-")
        clean_df = clean_df[clean_df["Date"].str.match(r"^\d{4}-\d{2}$", na=False)]
        
        # Filter range: 2016-01 to 2026-12
        clean_df = clean_df[(clean_df["Date"] >= "2016-01") & (clean_df["Date"] <= "2026-12")]
        
        # Map matching columns
        matched_mapping = {}
        for col in clean_df.columns:
            col_str = str(col).upper()
            for key, target_id in TARGET_COLS.items():
                if key in col_str and target_id not in matched_mapping.values():
                    matched_mapping[col] = target_id
                    
        clean_df = clean_df.rename(columns=matched_mapping)
        available_targets = [v for v in TARGET_COLS.values() if v in clean_df.columns]
        
        for col in available_targets:
            clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")
            
        clean_df = clean_df.sort_values(by="Date").reset_index(drop=True)
        records = clean_df[["Date"] + available_targets].to_dict(orient="records")
        
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "data": records
            }, f, indent=2, ensure_ascii=False)
            
        print(f"Successfully processed {len(records)} monthly records up to {records[-1]['Date']}.")
        
    except Exception as e:
        print(f"ETL Execution warning: {e}. Keeping current database cache.")

if __name__ == "__main__":
    fetch_and_update()
