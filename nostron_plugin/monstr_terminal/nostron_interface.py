import logging
import asyncio
from monstr.client.client import Client, ClientPool
from monstr.client.event_handlers import PrintEventHandler
from monstr.event.event import Event
from monstr.encrypt import Keys
 


async def fetch_events(relays=None,authors=None,MaxItems=200):            
    """
    doing a basic query using with to manage context
    :param relay:
    :return:
    """
    
    if relays is None or authors is None:
        return
    events = []
    all_events = []
    my_query={"limit": MaxItems,"authors": authors}
    for relay in relays:
        async with Client(relay) as c:
            events = await c.query(my_query)
            all_events = all_events + events
    return all_events
 
   


