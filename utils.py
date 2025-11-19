import os
from settings import STATIC_FILE_PATH, OUTPUT_PATH, PLAYWRIGHT_SESSION_PATH

def init_tmp_path():
    """
    Method to initialize the final output dirs. Creates dirs if not already created
    """

    os.makedirs(STATIC_FILE_PATH, exist_ok=True) # For cache, static files
    os.makedirs(OUTPUT_PATH, exist_ok=True) # For final output data
    os.makedirs(PLAYWRIGHT_SESSION_PATH, exist_ok=True) # For Playwright session data



def read_uszips_data(file_path:str = 'inputs/uszips.xlsx') -> list:
    """
    Reads the 'inputs/uszips.xlsx' file and returns its content as a list of dictionaries.
    Each dictionary represents a row, with column headers as keys.
    """
    import pandas as pd
    
    try:
        df = pd.read_excel(file_path)
        return df.to_dict(orient='records')
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return []
    except Exception as e:
        print(f"An error occurred while reading the Excel file: {e}")
        return []
