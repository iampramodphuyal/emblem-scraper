from .base_client import BaseClient
from urllib.parse import urlencode, quote
from logger.logger import get_logger
from .process_detail import process_provider
import json
import os
import random
import asyncio
from .helpers import save_content_as_json, solve_captcha
from configs import HEADERS
from settings import OUTPUT_PATH, SEQUENTIAL_FLOW



client = BaseClient(base_url="https://my.emblemhealth.com", use_proxy=True, retries=False)
logger = get_logger("Listing")


async def search_doctors(search_params: dict={}):
    logger.info("Starting search_doctors...")
    
    plan_type = search_params.get("planType", "")
    network_code = search_params.get("networkCode", "")
    page_size = 50
    zip_code = search_params.get("zipCode", "10001")
    
    os.makedirs(f"{OUTPUT_PATH}/listing", exist_ok=True)

    specialities = search_params.get("specialities", [])
    
    for _, sp in enumerate(specialities):
        service_type = sp['type']
        specialty = sp['code']
        
        # Reset page counter for each specialty
        page = 1
        total_pages = 1

        logger.info(f"Processing specialty: {specialty} ({service_type}) | Zip: {zip_code}")

        while page <= total_pages:
            start = (page - 1) * page_size
            logger.info(f"Fetching page {page} of {total_pages} | Zip: {zip_code} | Start: {start}")
            
            try:
                response = await make_request(page, service_type, specialty, search_params, start)
                
                # Check if response is empty (failed after retries)
                if not response:
                    logger.error(f"Failed to fetch results for {specialty} ({service_type}) page {page}")
                    page += 1
                    continue
                
                filename = f"raw_results_{specialty}_{service_type}_{zip_code}_page_{page}.json"
                save_content_as_json(response, f"{OUTPUT_PATH}/listing/{filename}")

                if page == 1:
                    total_results = response.get('totalRecords', 0)
                    if total_results == 0:
                        logger.info(f"No results found for {specialty} ({service_type}). | Zip: {zip_code}")
                        break
                    total_pages = (total_results // page_size) + (1 if total_results % page_size > 0 else 0)
                    logger.info(f"Total results: {total_results}, Total pages: {total_pages}")

                if SEQUENTIAL_FLOW:
                    results = response.get('providerList', [])
                    for result in results:
                        await process_provider(result, plan_type, network_code, service_type, specialty)

                page += 1
                
            except Exception as e:
                logger.error(f"Error processing page {page} for {specialty} ({service_type}): {e}")
                page += 1
                continue
        
        logger.info(f"Completed specialty: {specialty} ({service_type}) | Total pages processed: {page - 1}")
        

async def make_request(page: int, service_type: str, specialty: str, search_params: dict={}, start: int = 0) -> dict:
    zip_code = search_params.get("zipCode", "10001")
    distance = search_params.get("distance", "50mi")
    first_name = search_params.get("firstName", "")
    last_name = search_params.get("lastName", "")
    size = search_params.get("size", 50)
    plan_type = search_params.get("planType", "")
    network_code = search_params.get("networkCode", "")

    aura_context = {
        "mode": "PROD",
        "fwuid": "VFJhRGxfRlFsN29ySGg2SXFsaUZsQTFLcUUxeUY3ZVB6dE9hR0VheDVpb2cxMy4zMzU1NDQzMi41MDMzMTY0OA",
        "app": "siteforce:communityApp",
        "loaded": {
            "APPLICATION@markup://siteforce:communityApp": "1411_ppEHPnivv6tDSveOy-pRIw"
        },
        "dn": [],
        "globals": {},
        "uad": True
    }

    actionid = 188 if page == 1 else 188 + (page - 1) * 2
    
    max_attempts = 10
    
    for attempt in range(1, max_attempts + 1):
        initial_rand = random.randint(37, 42)
        random_increment = random.randint(4, 6)
        random_int = (page - 1) * random_increment
        rid = initial_rand if page == 1 else (initial_rand + random_int)
        
        url = f"/member/s/sfsites/aura?r={rid}&aura.ApexAction.execute=1"

        # captcha_token = await solve_captcha('2captcha')
        captcha_token = await solve_captcha()
    
        if not captcha_token:
            logger.error("Failed to solve captcha after multiple attempts")
            
        logger.debug(f"Using captcha token: {captcha_token}")
        
        payload = {
            "lastName": last_name,
            "tenantId": "EH",
            "planId": "",
            "planType": plan_type,
            "firstName": first_name,
            "ServiceType": service_type,
            "networkId": "",
            "networkCode": network_code,
            "distance": distance,
            "zipCode": zip_code,
            "providerSpeciality": specialty,
            "from": start,
            "size": size,
            "fhn": "",
            "captchaResp": captcha_token,
        }
        
        message = {
            "actions": [{
                "id": f"{actionid};a",
                "descriptor": "aura://ApexActionController/ACTION$execute",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "namespace": "vlocity_ins",
                    "classname": "BusinessProcessDisplayController",
                    "method": "GenericInvoke2NoCont",
                    "params": {
                        "input": json.dumps(payload, separators=(',', ':')),
                        "options": "{}",
                        "sClassName": "vlocity_ins.IntegrationProcedureService",
                        "sMethodName": "Member_findDoctor",
                    },
                    "cacheable": False,
                    "isContinuation": False,
                },
            }]
        }

        params_str = urlencode({
            "message": json.dumps(message, separators=(',', ':')),
            "aura.context": json.dumps(aura_context, separators=(',', ':')),
            "aura.pageURI": '',
            "aura.token": "null"
        }, quote_via=quote)

        logger.debug(f"Making request to {url} | Attempt {attempt}/{max_attempts}")

        # Reduced delay - original was too long for concurrent processing
        await asyncio.sleep(random.uniform(0.5, 1.5))

        try:
            response = await client._request("POST",
                url,
                data=params_str,
                headers=HEADERS
            )

            resp = json.loads(response['body'])
            data = [
                action for action in resp.get("actions", [])
                if "returnValue" in action and "returnValue" in action["returnValue"]
            ]

            for d in data:
                if d['state'] != "SUCCESS":
                    continue
                results = d['returnValue']['returnValue']
                results = json.loads(results).get("IPResult", [])

                if results:
                    logger.debug(f"Successfully fetched results | Page: {page} | Specialty: {specialty}")
                    return results

        except Exception as exc:
            logger.error(f"Error during request: {exc} | Attempt {attempt}/{max_attempts}")
            if attempt >= max_attempts:
                logger.critical(f"Max retries reached. Failing the request. | Zip: {zip_code}, Specialty: {specialty} | Plan Type: {plan_type}")
                return {}
            else:
                logger.info(f"Retrying... (Attempt {attempt}/{max_attempts})")
                await asyncio.sleep(random.uniform(1, 2))  # Add delay before retry
    
    return {}