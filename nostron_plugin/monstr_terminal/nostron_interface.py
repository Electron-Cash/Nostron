import logging
import asyncio
from monstr.client.client import Client, ClientPool
from monstr.client.event_handlers import PrintEventHandler
from monstr.event.event import Event
from monstr.encrypt import Keys
 

async def fetch_group_chats(relays=None,MaxItems=1000):
    if relays is None:
        return None
    events = []
    all_events = []
    my_query={"limit": MaxItems,"kinds": [40]}
    for relay in relays:
        try:
            async with Client(relay) as c:
                events = await c.query(my_query)
                all_events = all_events + events
        except:
            pass
    return all_events


async def fetch_group_chat_messages(relays=None,MaxItems=1000,e_tag=None):
    
    
    # Must have a relay and a group. the e tag is the origin with kind=40
    if relays is None:
        return None
    if e_tag is None:
        return None
        
    events = []
    all_events = []
    e_tag_list = []
    e_tag_list.append(e_tag)
    my_query={"limit": MaxItems,"kinds": [42],"#e": e_tag_list } 
    for relay in relays:
        try:
            async with Client(relay) as c:
                events = await c.query(my_query)
                all_events = all_events + events
        except:
            pass
    return all_events

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
        try:
            async with Client(relay) as c:
                events = await c.query(my_query)
                all_events = all_events + events
        except:
            pass
    return all_events
 
   


