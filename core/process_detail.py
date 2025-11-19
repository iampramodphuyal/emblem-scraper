from .base_client import BaseClient
from urllib.parse import urlencode, quote
from logger.logger import get_logger
import json
import os
import random
import asyncio
from .helpers import two_cap, capsolver, save_content_as_json, fake_solve_captcha
from configs import HEADERS
from settings import OUTPUT_PATH, SEQUENTIAL_FLOW
from cache import CacheHandler

cache = CacheHandler(use_existing_cache=True)
client = BaseClient(base_url="https://my.emblemhealth.com", use_proxy=True, retries=False)
logger = get_logger("Process Detail")

async def process_provider(provider: dict, plan_type:str, network_code:str, service_type:str, provider_speciality:str) -> bool:
    """
    Asynchronously processes a single provider's details based on the given parameters.

    Args:
        provider (dict): A dictionary containing the provider's information, including 'ProviderId' and 'providerFullName'.
        plan_type (str): The type of plan associated with the provider.
        network_code (str): The network code for the provider.
        service_type (str): The type of service the provider offers.
        provider_speciality (str): The speciality of the provider.

    Returns:
        bool: True if the provider processing is successful, False otherwise.
    """

    provider_id = provider['ProviderId']
    if cache.exists(provider_id):
        logger.info(f"Provider {provider['providerFullName']} | ID: {provider['ProviderId']} already processed. Skipping.")
        return True
        
    logger.info(f"Processing provider {provider['providerFullName']} | ID: {provider['ProviderId']}")
    aura_context = {"mode":"PROD","fwuid":"VFJhRGxfRlFsN29ySGg2SXFsaUZsQTFLcUUxeUY3ZVB6dE9hR0VheDVpb2cxMy4zMzU1NDQzMi41MDMzMTY0OA","app":"siteforce:communityApp","loaded":{"APPLICATION@markup://siteforce:communityApp":"1411_ppEHPnivv6tDSveOy-pRIw"},"dn":[],"globals":{},"uad":True}
    
    inputs = {
        "providerId":f"{provider_id}",
        "tenantId":"EH",
        "planType":f"{plan_type}",
        "networkCode":f"{network_code}",
        "fhn":"",
        "ServiceType":f"{service_type}",
        "providerSpeciality":""
    }

    message = {
        "actions": [
            {
                "id": "198;a",
                "descriptor": "aura://ApexActionController/ACTION$execute",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "namespace": "vlocity_ins",
                    "classname": "BusinessProcessDisplayController",
                    "method": "GenericInvoke2NoCont",
                    "params": {
                        "input": json.dumps(inputs, separators=(',', ':')),
                        "options": "{}",
                        "sClassName": "vlocity_ins.IntegrationProcedureService",
                        "sMethodName": "Member_providerDetails"
                    },
                    "cacheable": False,
                    "isContinuation": False
                }
            }
        ]
    }
    
    payload = {
        "message": json.dumps(message, separators=(',', ':')),
        "aura.context": json.dumps(aura_context, separators=(',', ':')),
        "aura.pageURI" : "",
        "aura.token":"null"
    }
    
    payload = urlencode(payload, quote_via=quote)
    rid = random.randint(43, 47)
    url = f"/member/s/sfsites/aura?r={rid}&aura.ApexAction.execute=1"
    
    os.makedirs(f"{OUTPUT_PATH}/detail", exist_ok=True)

    for attempt in range(1, 11):
        logger.debug(f"Making request to {url} | Attempt {attempt}")
        try:
            response = await client._request("POST",
            url,
            data=payload,
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
                    filename = f"raw_results_{provider_id}.json"
                    save_content_as_json(response, f"{OUTPUT_PATH}/detail/{filename}")
                    return True

        except Exception as exc:
            logger.error(f"Error during search_doctors: {exc}")
            if attempt >=10:
                logger.critical(f"Max retries reached. Failing the request. | Provider ID: {provider_id} | Plan Type: {plan_type} | Network Code: {network_code} | Service Type: {service_type} | Provider Speciality: {provider_speciality}")
            else:
                logger.info(f"Retrying... (Attempt {attempt}/10)")
    
    return False