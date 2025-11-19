import asyncio
import json
import gc
import logging
from utils import init_tmp_path, read_uszips_data
from core.process_listing import search_doctors
from settings import SEMAPHORE, BATCH_SIZE

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

with open("inputs/raw_files/specialities-doctor-types.json", "r") as f:
    DOCTOR_SPECIALITIES = [{**d, "type": "Doctor"} for d in json.load(f)]

with open("inputs/raw_files/specialities-pcp-types.json", "r") as f:
    PCP_SPECIALITIES = [{**d, "type": "PCP"} for d in json.load(f)]

with open("inputs/raw_files/specialities-dental-types.json", "r") as f:
    DENTAL_SPECIALITIES = [{**d, "type": "Dental"} for d in json.load(f)]

with open("inputs/raw_files/plans.json", "r") as f:
    PLANS = json.load(f)

async def main(inputs:dict):
    dental_specialities = [{**d, "type": "Dental"} for d in DENTAL_SPECIALITIES]
    doctor_specialities = [{**d, "type": "Doctor"} for d in DOCTOR_SPECIALITIES]
    pcp_specialities = [{**d, "type": "PCP"} for d in PCP_SPECIALITIES]

    specialities = doctor_specialities + pcp_specialities
    
    for plan in PLANS:
        logger.info(f"Processing plan: {plan}")

        plan_type = "HIP"
        if plan['LobMctrType'] == 1003:
            plan_type = "GHI" 
        
        coverage_type = plan['CoverageType']
        if coverage_type == 'D':
            specialities = dental_specialities
     
        await search_doctors(search_params={
            "zipCode": f"{inputs['zip']}",
            "planType": plan_type,
            "networkCode": plan['NetworkCode'],
            "size": 50,
            "specialities" : specialities,
            "coverage_type": coverage_type
           })

 

if __name__ == "__main__":
    init_tmp_path()
    inputs = read_uszips_data()
    
    semaphore = asyncio.Semaphore(SEMAPHORE)  # Controls concurrency within batch

    async def limited_main(input_item):
        async with semaphore:
            await main(input_item)
            gc.collect()  # free memory after each item

    async def process_batch(batch):
        """Process a single batch with controlled concurrency"""
        logger.info(f"Processing {len(batch)} items in this batch with {SEMAPHORE} concurrent tasks")
        await asyncio.gather(
            *(limited_main(input_item) for input_item in batch), 
            return_exceptions=True
        )
        gc.collect()  # free memory after each batch

    async def process_all_batches():
        """Process all inputs in batches sequentially"""
        total_batches = (len(inputs) + BATCH_SIZE - 1) // BATCH_SIZE
        
        for i in range(0, len(inputs), BATCH_SIZE):
            batch = inputs[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            
            logger.info(f"Starting batch {batch_num}/{total_batches} ({len(batch)} items)")
            await process_batch(batch)
            logger.info(f"Completed batch {batch_num}/{total_batches}")

    asyncio.run(process_all_batches())