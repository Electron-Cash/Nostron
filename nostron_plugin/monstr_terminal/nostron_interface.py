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
        
    
    my_query={"limit": MaxItems,"authors": authors}
    async with ClientPool(relays) as c:
        events = await c.query(my_query)
     
    
    return events
 
   


