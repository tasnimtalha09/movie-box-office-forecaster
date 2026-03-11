## This function was built with the help of AI

def aggregate_master(df, movie_col = "Release"):
    # Importing the necessary library
    import pandas as pd
    
    # Sort by movie and date to ensure correct ordering
    df_sorted = df.sort_values([movie_col, "Date"]).reset_index(drop = True)
    
    # Group by movie and take first 7 days for each
    def get_first_7_days(group):
        # Take only first 7 days
        first_7 = group.head(7)
        
        if len(first_7) == 0:
            return None
            
        # Aggregate the data
        aggregated = {
            movie_col: first_7[movie_col].iloc[0],           # Movie name
            "Date": first_7["Date"].min(),                   # Opening date (first date)
            "Daily": first_7["Daily"].sum(),                 # Total 7-day revenue
            "Theaters": first_7["Theaters"].max(),           # Peak theater count
            "Avg": first_7["Avg"].mean().round(3),           # Average per-theater revenue
            "To_Date": first_7["To_Date"].iloc[-1],          # Cumulative at day 7
            "Distributor": first_7["Distributor"].iloc[0],   # Distributor
            "TMDB_ID": first_7["TMDB_ID"].iloc[0]            # TMDB ID
        }
        
        return pd.Series(aggregated)
    
    # Apply aggregation to each movie
    aggregate = df_sorted.groupby(movie_col).apply(get_first_7_days).reset_index(drop = True)
    
    # Remove movies with no data
    aggregate.sort_values(by = "Date", inplace = True)
    aggregate = aggregate.dropna().reset_index(drop = True)
    
    return aggregate