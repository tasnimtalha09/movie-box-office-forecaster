## This scrapper was built with the help of AI

def import_movies_01(start_year, end_year):
    # Import the required libraries
    import pandas as pd
    import time
    import requests

    # Creating an empty list
    all_years = []

    # Creating a loop that will pull yearly data
    for year in range(start_year, end_year):
        print(f"\nScraping data for year {year}...")
        url = f"https://www.boxofficemojo.com/daily/{year}/?view=year"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        # Sending the request to read the website data
        try:
            r = requests.get(url = url, headers = headers, timeout = 5)
            r.raise_for_status()

            # Finding the number of tables present the url
            tables = pd.read_html(r.text)
            if len(tables) == 1:
                print(f"Found {len(tables)} table")
            else:
                print(f"Found {len(tables)} tables")

            # Printing the first table that we find and add a year column
            df = tables[0]
            df["Year"] = year

            # Listing that table in the list
            all_years.append(df)

            # Having some rest between multiple requests
            time.sleep(2)

        # Error message in case some years are missed
        except Exception as e:
            print(f"Failed for year {year}")
            continue
    
    # Concatenating all the datasets into one major dataset
    dataset = pd.concat(all_years, ignore_index = True)
 
    # Starting the cleaning steps
    print(f"Cleaning the {year} dataset...")


    # Cleaning the date columns and creating one unified one
    # 1. Extract the 'Mon DD' part (handles 1–31)
    dataset["Date_cleaned"] = dataset["Date"].str.extract(r"([A-Za-z]{3}\s*\d{1,2})")[0].str.strip()

    # 2. Extract anything AFTER the day (if any)
    dataset["Special_Day"] = dataset["Date"].str.extract(r"[A-Za-z]{3}\s*\d{1,2}(.*)")[0].str.strip()
    dataset["Special_Day"].replace("", pd.NA, inplace=True)
    dataset["Date_combined"] = pd.to_datetime(
            dataset["Date_cleaned"] + " " + dataset["Year"].astype(str),
            format = "%b %d %Y",
            errors = "coerce"
    )

    # Converting the gross columns into numeric
    gross_cols = ["Top 10 Gross", "Gross"]
    for col in gross_cols:
        dataset[col] = (
            dataset[col].astype(str)
            .str.replace("$", "", regex = False)
            .str.replace(",", "", regex = False)
        )
    dataset[col] = pd.to_numeric(dataset[col], errors = "coerce")

    # Converting the % columns into numeric
    percentage_cols = ["%± YD", "%± LW"]
    for col in percentage_cols:
        percentage_cleaned = (
            dataset[col].astype(str)
            .str.strip()
            .str.replace("%", "", regex = False)
            .str.replace(",", "", regex = False)
        )

        pct = pd.to_numeric(arg = percentage_cleaned, errors = "coerce")
        dataset[col] = 1 + round(number = (pct/100), ndigits = 3)

    # Adding a movie_id column
    dataset["Movie_ID"] = pd.factorize(values = dataset["Top_Release"])[0] + 1
    
    # Dropping the unnecessary columns
    cols_to_drop = ["Date_cleaned", "Day #", "Date", "Year"]
    dataset.drop(columns = cols_to_drop, inplace = True)

    # Renaming the date column
    dataset = dataset.rename(columns = {
        "Date_combined": "Date",
        "#1 Release": "Top_Release",
        "%± YD": "Change_per_Day",
        "%± LW": "Change_per_Week",
        "Releases": "No_of_Releases",
        "Gross": "Top_Release_Gross",
        "Top 10 Gross": "Top_10_Gross"
        }
    )

    # Reordering the columns
    dataset = dataset[["Date", "Day","No_of_Releases", "Movie_ID" "Top_Release", "Top_Release_Gross", "Top 10 Gross", "Change_per_Day", "Change_per_Week", "Special_Day"]]

    # Sort the dataset by date
    dataset.sort_values(by = "Date", ascending = False, inplace = True)

    # Printing the output in a CSV file
    dataset.to_csv("Movies.csv", index = False, date_format = "%Y-%m-%d")