"""Example usage of pyhomely."""

import asyncio
import logging
import os

import aiohttp

from pyhomely.client import ApiClient

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s:%(name)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

LOGGER = logging.getLogger("example")


async def example() -> None:
    """Example usage of pyhomely."""
    async with aiohttp.ClientSession() as client_session:
        client = ApiClient(
            username=os.environ["HOMELY_USERNAME"],
            password=os.environ["HOMELY_PASSWORD"],
            client_session=client_session,
        )
        locations = await client.locations()
        for location in locations:
            home = await client.home(location["locationId"])
            LOGGER.info(
                "%s: %s (%s devices)",
                location["locationId"],
                home["name"],
                len(home["devices"]),
            )


asyncio.run(example())
