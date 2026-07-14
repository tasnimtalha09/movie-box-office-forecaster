## This scrapper was built with the help of AI

def import_movies(year):
    # Importing the required libraries
    import pandas as pd
    import time
    from datetime import datetime, timedelta
    from boxoffice_api import BoxOffice

    # Configuration
    API_SLEEP = 0.25
    start_date = datetime(year, 1, 1)
    end_date   = datetime(year, 12, 31)

    # Revenue and percent columns to clean
    REV_COLS = ["Daily", "Avg", "To Date"]
    PCT_COLS = ["%± YD", "%± LW"]

    # Initialize API
    box = BoxOffice(outputformat = "DF")

    # Pull daily data
    all_days = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        try:
            df = box.get_daily(date = date_str)
            df["Date"] = date_str
            all_days.append(df)
            print(f"✓ Pulled data for {date_str} ({len(df)} records)")
        except Exception as e:
            print(f"⚠ Skipped {date_str}: {e}")
        time.sleep(API_SLEEP)
        current_date += timedelta(days = 1)

    # Combine results
    if not all_days:
        raise SystemExit("No data collected.")

    final_df = pd.concat(all_days, ignore_index = True)
    print("Combined dataset shape:", final_df.shape)


    # Data Cleaning
    # 1. Clean revenue-like columns: remove $ and commas, convert to numeric
    for col in REV_COLS:
        if col in final_df.columns:
            final_df[col] = (
                final_df[col]
                .astype(str)
                .str.replace("$", "", regex =False)
                .str.replace(",", "", regex = False)
            )
            final_df[col] = pd.to_numeric(final_df[col], errors = "coerce")

    # 2. Clean percent columns: remove %, convert to float, then to multiplier (1 + p/100)
    for col in PCT_COLS:
        if col in final_df.columns:
            cleaned = (
                final_df[col]
                .astype(str)
                .str.strip()
                .str.replace("%", "", regex =False)
                .str.replace(",", "", regex = False)
                .replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA})
            )
            pct = pd.to_numeric(cleaned, errors="coerce")
            final_df[col] = (1 + (pct / 100.0)).round(3)  # e.g., -62.8% -> 0.372

    # 3. Theaters → remove commas and convert to int-like numeric
    if "Theaters" in final_df.columns:
        final_df["Theaters"] = (
            final_df["Theaters"]
            .astype(str)
            .str.replace(",", "", regex = False)
        )
        final_df["Theaters"] = pd.to_numeric(final_df["Theaters"], errors = "coerce").astype("Int64")

    # 4. Rename percent columns to friendlier names
    final_df.rename(columns = {
        "%± YD": "Change_per_Day",
        "%± LW": "Change_per_Week",
        "To Date": "To_Date"
        }, inplace = True)

    # 5. Dropping two columns
    final_df.drop(columns = ["TD", "YD"], inplace = True)

    # 6. Rearranging the columns
    final_df = final_df[["Date", "Release", "Daily", "Change_per_Day", "Change_per_Week", "Theaters", "Avg", "To_Date", "Days", "Distributor"]]

    # Sorting the dataset
    final_df.sort_values(by = "Date", ascending = False, inplace = True)

    # Save cleaned file
    out_fn = f"boxoffice_{year}.csv"
    final_df.to_csv(out_fn, index = False, date_format = "%Y-%m-%d")

    # Printing finish statement
    print(f"Saved → {out_fn}")