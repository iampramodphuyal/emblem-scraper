# Emblem Scraper

This project is an asynchronous web scraper designed to extract provider (doctor and dental) listing and detail information from the EmblemHealth website. It features robust retry mechanisms, proxy support, CAPTCHA solving capabilities, and an LMDB-backed caching system.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Input Data](#input-data)
- [Output Data](#output-data)
- [Usage](#usage)
- [Core Logic Overview](#core-logic-overview)
- [Troubleshooting and Notes](#troubleshooting-and-notes)

## Features

*   **Asynchronous HTTP Requests:** Utilizes `httpx` for efficient, non-blocking web requests.
*   **Retry Mechanism:** Built-in exponential backoff for failed requests to improve resilience.
*   **Proxy Support:** Configurable proxy settings for rotating IPs or bypassing geo-restrictions.
*   **CAPTCHA Solving:** Integrates with `2Captcha` and `Capsolver` services, and includes a Playwright-based "fake" CAPTCHA solver for reCAPTCHA v3.
*   **LMDB Caching:** Uses `lmdb` for efficient caching of previously processed items.
*   **Structured Input:** Reads plan and specialty data from JSON files and zip codes from an Excel file.
*   **Modular Design:** Separated concerns for base client, listing processing, detail processing, and utility functions.
*   **Logging:** Comprehensive logging to console and rotating files, including a dedicated log for failed URLs.
*   **Concurrency Control:** Manages concurrent requests using semaphores and batch processing.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-repo/emblem_scraper.git
    cd emblem_scraper
    ```

2.  **Install dependencies using Pipenv:**
    If you don't have Pipenv installed, install it first:
    ```bash
    pip install pipenv
    ```
    Then, install project dependencies:
    ```bash
    pipenv install
    ```
    Alternatively, you can install from `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Playwright browsers (if using the fake CAPTCHA solver):**
    ```bash
    playwright install
    ```

## Configuration

The project uses environment variables for sensitive information and configurable settings, loaded from a `.env` file. Create a `.env` file in the project root with the following (or similar) content:

```dotenv
# API Keys for CAPTCHA solving services
APIKEY_2CAPTCHA="YOUR_2CAPTCHA_API_KEY"
CAPSOLVER_API_KEY="YOUR_CAPSOLVER_API_KEY"
CAPTCHA_SITE_KEY="YOUR_EMBLEMHEALTH_CAPTCHA_SITE_KEY" # Example: 6LcNq-wpAAAAAPupbdPcNjDpmhx4_HbfSmRW2ME4

# Proxy Settings (optional)
PROXY_HOST="your_proxy_host"
PROXY_PORT="your_proxy_port"
PROXY_USERNAME="your_proxy_username"
PROXY_PASSWORD="your_proxy_password"

# Browser Settings
HEADLESS="False" # Set to "True" to run Playwright in headless mode

# Output Paths
OUTPUT_PATH="outputs/raw"
STATIC_FILE_PATH="outputs/static"
TMP_PATH="outputs/tmp"

# Playwright Session Path
PLAYWRIGHT_SESSION_PATH="sessions/recaptcha_profile"

# Crawler Flow
SEQUENTIAL_FLOW="True" # Set to "False" for parallel processing of provider details

# Concurrency Control
SEMAPHORE="5" # Max concurrent tasks for processing input items
BATCH_SIZE="50" # Number of input items to process in each batch
```

**Key settings in `settings.py`:**

*   `API_KEY`, `DB_URL`, `DEBUG`: General application settings.
*   `PROXY_HOST`, `PROXY_PORT`, `PROXY_USERNAME`, `PROXY_PASSWORD`: Proxy configuration.
*   `HEADLESS`: Controls Playwright browser visibility.
*   `OUTPUT_PATH`, `STATIC_FILE_PATH`, `TMP_PATH`: Defines where various output files and temporary data are stored.
*   `PLAYWRIGHT_SESSION_PATH`: Directory for Playwright browser session data.
*   `SEQUENTIAL_FLOW`: A boolean flag (`True`/`False`) that determines if provider details are processed sequentially after listing, or if only listings are scraped. If `True`, `process_provider` is called for each result from `search_doctors`.
*   `SEMAPHORE`: Limits the number of concurrent `main` function executions.
*   `BATCH_SIZE`: Determines how many input items are processed in a single batch before moving to the next.

## Input Data

Input data is stored in the `inputs/` directory:

*   `inputs/uszips.xlsx`: An Excel file containing a list of zip codes to be used for the search. Each row should represent a zip code.
*   `inputs/raw_files/plans.json`: Contains a list of health plans with details like `NetworkCode`, `LobMctrType`, `CoverageType`, etc.
*   `inputs/raw_files/specialities-doctor-types.json`: Defines various doctor specialties.
*   `inputs/raw_files/specialities-pcp-types.json`: Defines various Primary Care Provider (PCP) specialties.
*   `inputs/raw_files/specialities-dental-types.json`: Defines various dental specialties.
*   `inputs/raw_files/specialityTypes.json`: A general mapping of specialty names to types (e.g., "Doctor", "PCP").

These JSON files are loaded at the start of `main.py` to configure the search parameters.

## Output Data

Scraped data and logs are stored in the `outputs/` and `logs/` directories:

*   `outputs/raw/listing/`: Raw JSON responses from the provider listing searches are saved here. Filenames typically follow the pattern `raw_results_{specialty}_{service_type}_{zip_code}_page_{page}.json`.
*   `outputs/raw/detail/`: Raw JSON responses containing detailed information for each provider are saved here. Filenames typically follow the pattern `raw_results_{provider_id}.json`.
*   `logs/`: Contains application logs, including a dedicated `failed_urls.log` for critical errors.
*   `sessions/recaptcha_profile/`: Playwright session data is stored here to maintain browser state across runs if needed for CAPTCHA solving.
*   `lmdb_cache/`: The LMDB cache database used by `cache.py`.

## Usage

To run the scraper, execute `main.py`:

```bash
pipenv run python main.py
```
or
```bash
python main.py
```

The script will:
1. Initialize output directories.
2. Read zip codes from `inputs/uszips.xlsx`.
3. Iterate through each zip code and each defined health plan.
4. For each plan, it will iterate through relevant specialties (doctor, PCP, or dental based on `CoverageType`).
5. It will then call `search_doctors` to fetch provider listings.
6. If `SEQUENTIAL_FLOW` is `True`, it will then call `process_provider` for each listed provider to fetch detailed information.

## Core Logic Overview

### `main.py`
This is the entry point of the application. It orchestrates the entire scraping process:
- Loads all static input JSON files (`plans.json`, `specialities-doctor-types.json`, etc.).
- Reads zip codes from `uszips.xlsx`.
- Iterates through each zip code and each plan.
- Determines the appropriate specialties based on the plan's `CoverageType`.
- Calls `core.process_listing.search_doctors` for each combination of zip code, plan, and specialty.
- Manages concurrency using `asyncio.Semaphore` and processes inputs in batches defined by `BATCH_SIZE`.

### `core/process_listing.py`
Contains the `search_doctors` function, which is responsible for:
- Constructing the request payload for searching provider listings on the EmblemHealth website.
- Handling pagination to retrieve all available listings for a given search query.
- Calling CAPTCHA solving functions (`capsolver` or `fake_solve_captcha`) to obtain a CAPTCHA token.
- Making HTTP POST requests using `BaseClient`.
- Saving raw listing responses to `outputs/raw/listing/`.
- Optionally, if `SEQUENTIAL_FLOW` is `True`, it calls `core.process_detail.process_provider` for each provider found in the listing.

### `core/process_detail.py`
Contains the `process_provider` function, which is responsible for:
- Constructing the request payload to fetch detailed information for a specific provider using their `ProviderId`.
- Making HTTP POST requests using `BaseClient`.
- Saving raw detail responses to `outputs/raw/detail/`.

### `core/base_client.py`
Provides the `BaseClient` class, an asynchronous HTTP client wrapper:
- Handles HTTP requests with configurable retries and exponential backoff.
- Integrates proxy support using environment variables (`PROXY_HOST`, `PROXY_PORT`, etc.).
- Generates browser-like headers using `browserforge`.

### `core/helpers.py`
A collection of utility functions:
- `two_cap()` and `capsolver()`: Functions to interact with 2Captcha and Capsolver APIs for CAPTCHA solving.
- `fake_solve_captcha()`: Uses Playwright to programmatically navigate to the CAPTCHA page and execute JavaScript to obtain a token. This is a more robust solution for reCAPTCHA v3.
- `make_fwuid()` and `generate_request_ids()`: Generates unique IDs required for the EmblemHealth API requests.
- `save_content_as_json()`: Helper to save Python objects as formatted JSON files.
- `ensure_dir_exists()`: Ensures a directory path exists, creating it if necessary.

### `cache.py`
Implements `CacheHandler`, a simple LMDB-backed key-value store:
- Used to check if a key (e.g., a provider ID or a search query) has been processed before.
- Prevents redundant requests and can be used to manage state across runs.
- Supports context manager usage for automatic closing.

### `logger/logger.py`
Configures a custom logging system:
- Sets up console output and rotating file handlers.
- Includes a dedicated handler for `CRITICAL` level messages to `failed_urls.log`.

### `utils.py`
Contains general utility functions:
- `init_tmp_path()`: Creates necessary output and session directories.
- `read_uszips_data()`: Reads zip codes from the `inputs/uszips.xlsx` Excel file using `pandas`.

## Troubleshooting and Notes

*   **CAPTCHA Issues:** If you encounter frequent CAPTCHA failures, ensure your `CAPTCHA_SITE_KEY` is correct and your CAPTCHA solving service API keys are valid and have sufficient balance. The `fake_solve_captcha` function using Playwright is designed to be more robust for reCAPTCHA v3.
*   **Proxy Configuration:** Verify your proxy settings in the `.env` file. Incorrect proxy details will lead to connection errors.
*   **Rate Limiting:** The `BaseClient` includes retry logic, but aggressive scraping might still lead to IP bans or temporary blocks. Adjust `SEMAPHORE` and `BATCH_SIZE` to control the request rate.
*   **Playwright Headless Mode:** If `HEADLESS` is `False`, a browser window will open during CAPTCHA solving, which can help in debugging. For production, `True` is recommended.
*   **Session Data:** The `PLAYWRIGHT_SESSION_PATH` stores browser session data. Clearing this directory might be necessary if you encounter persistent browser-related issues.
*   **Memory Usage:** Processing large numbers of providers or running with high concurrency might consume significant memory. The `gc.collect()` calls in `main.py` are intended to help manage this.
*   **Error Logging:** Check `logs/scraper_*.log` for general application logs and `logs/failed_urls.log` for critical errors related to failed requests.
*   **Data Structure:** The output JSON files (`outputs/raw/listing/` and `outputs/raw/detail/`) contain the raw responses from the EmblemHealth API. You may need to further process these JSON structures to extract specific data points.
