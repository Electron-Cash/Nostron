from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    pass
import logging
import asyncio
import aiohttp
from aiohttp import WSCloseCode
from aiohttp import web, http_websocket
import json
from json import JSONDecodeError
from monstr.event.event import Event
from monstr.event.persist import RelayEventStoreInterface, ARelayEventStoreInterface
from monstr.encrypt import Keys
from monstr.relay.accept_handlers import AcceptReqHandler
from monstr.relay.exceptions import NostrCommandException, NostrNoticeException

# from sqlite3 import IntegrityError
# try:
#     import psycopg2.errors as pg_errors
# except:
#     pg_errors = None


class Relay:
    """
        implements monstr relay protocol
        NIP-01      -   basic protocol
                        https://github.com/fiatjaf/nostr/blob/master/nips/01.md
        NIP-02      -   contact list
                        https://github.com/fiatjaf/nostr/blob/master/nips/02.md
        NIP-09      -   event deletions depends on the store
                        delete_mode=DeleteMode.DEL_FLAG probbably best option as this will mark the event as deleted
                        but also it won't be possible to repost.
                        https://github.com/fiatjaf/nostr/blob/master/nips/09.md
        NIP-11      -   TODO: Relay Information Document
                        https://github.com/fiatjaf/nostr/blob/master/nips/11.md
        NIP-12          generic querie tags, todo but should be easy.... test with shared
                        https://github.com/fiatjaf/nostr/blob/master/nips/12.md

        NIP-15      -   send 'EOSE' msg after sending the final event for a subscription
                        https://github.com/nostr-protocol/nips/blob/master/15.md

        NIP-16      -   ephemeral and replaceable events, depends on the store
                        https://github.com/nostr-protocol/nips/blob/master/16.md

        for NIPS n,n... whats actually being implemented will be decided by the store/properties it was created with
        e.g. delete example....
        For NIP-12 the relay will check with the store for those NIPs

        TODO: write some test code for each NIP...

    """
    VALID_CMDS = ['EVENT', 'REQ', 'CLOSE']

    def __init__(self, store: RelayEventStoreInterface,
                 accept_req_handler=None,
                 max_sub=10,
                 name: str = None,
                 description: str = None,
                 pubkey: str = None,
                 contact: str = None,
                 enable_nip15=False,
                 ack_events=True):


        # open web sockets
        self._ws_id = 0
        self._ws = {}

        # if you don't hand in a store then nothing is being saved and events will only be seen as they come in
        self._store = store
        if store and not isinstance(store, (ARelayEventStoreInterface, RelayEventStoreInterface)):
            raise Exception('Relay::__init__ store should implement ARelayEventStoreInterface or RelayEventStoreInterface')

        # max subs allowed per websocket
        self._max_sub = max_sub

        # if True we'll send and OK events on accepting event and storing them
        self._ack_events = ack_events

        # by default when we recieve requests as long as the event has a valid sig we accept
        # (Prob we should also have a future timestamp requirement maybe + a few mins to allow for system clock drift
        # but in real world relay will probably want to protect itself more e.g. set max length on
        # event content, restrict to set kinds or even only allow set pubkeys to posts
        # self._accept_req can be a single class or [] of handlers that are called and the event will
        # it'll throw and return a NOTICE evt if msg not accepted (maybe we'd want option to just drop and do nothing?)
        self._accept_req = accept_req_handler
        if self._accept_req is None:
            # accepts everything
            self._accept_req = [AcceptReqHandler()]
        # convert to array of only single class handed in
        if not hasattr(self._accept_req, '__iter__'):
            self._accept_req = [self._accept_req]

        # this is the server that we run as, it's created after calling start()
        # default is localhost:8080
        self._server: web.Application = None
        self._runner: web.AppRunner = None
        self._host = None
        self._port = None
        self._end_point = None

        if pubkey is not None and not Keys.is_key(pubkey):
            raise Exception('given contact pubkey is not correct: %s' % pubkey)

        # deletes
        self._nip09 = self._store and self._store.is_NIP09()
        # EOSE
        self._nip15 = enable_nip15
        # replacable and transient event ranges
        self._nip16 = self._store and self._store.is_NIP16()


        nips = [1, 2, 11]
        if self._nip15:
            nips.append(15)
        if self._nip09:
            nips.append(9)
        if self._nip16:
            nips.append(16)

        nips.sort()

        logging.info('Relay::__init__ maxsub=%s '
                     'EOSE enabled(NIP15)=%s, Deletes(NIP9)=%s, Event treatment(NIP16)=%s' % (self._max_sub,
                                                                                              self._nip15,
                                                                                              self._nip09,
                                                                                              self._nip16))


        self._relay_information = {
            'software': 'https://github.com/monty888/nostrpy',
            'version': '0.1',
            'supported_nips': nips
        }
        if name:
            self._relay_information['name'] = name
        if description:
            self._relay_information['description'] = description
        if contact:
            self._relay_information['contact'] = contact
        if pubkey is not None:
            if Keys.is_key(pubkey):
                raise Exception('given contact pubkey is not correct: %s' % pubkey)
            self._relay_information['pubkey'] = pubkey

    def _starter(self, host='localhost', port=8080, end_point='/', routes=None):
        # self._app.route(end_point, callback=self._handle_websocket)
        self._host = host
        self._port = port
        self._end_point = end_point

        async def on_shutdown(app):
            logging.info('Relay::on_shutdown - closing open websockets')
            to_close = [self._ws[i]['ws'] for i in self._ws]
            for ws in to_close:
                await ws.close(code=WSCloseCode.GOING_AWAY,
                               message='Server shutdown')

        self._server = web.Application()
        self._server.on_shutdown.append(on_shutdown)



        # self._server.router.add_route('*', '/{path_info:.*}', self._wsgi_handler)

        my_routes = [web.get(self._end_point, handler=self._websocket_handler)]
        if routes:
            my_routes = my_routes + routes
        self._server.add_routes(my_routes)

    async def start(self, host='localhost', port=8080, end_point='/', routes=None, block=True):
        logging.info('Relay::start %s:%s%s block=%s' % (host, port, end_point, block))

        self._starter(host, port, end_point, routes)

        self._runner = web.AppRunner(self._server)
        await self._runner.setup()
        site = web.TCPSite(self._runner,
                           host=self._host,
                           port=self._port)
        await site.start()

        # probably there is a better way to do this but was having problems mixing web.run_app with
        # async db etc... this does mean that start and start_background are now the same
        if block:
            while True:
                await asyncio.sleep(0.1)

    async def start_background(self, host='localhost', port=8080, end_point='/', routes=None):
        # remove this method eventually
        await self.start(host=host,
                         port=port,
                         end_point=end_point,
                         block=False)

    @property
    def url(self):
        return 'ws://%s:%s%s' % (self._host,
                                 self._port,
                                 self._end_point)

    @property
    def store(self):
        return self._store

    @property
    def server(self) -> web.Application:
        return self._server

    @property
    def started(self):
        ret = False
        if self._runner is None and self._server is not None:
            return True
        elif self._runner is not None:
            return True
        return ret

    def end(self):
        # note to call this you'd have to have called start in a thread or similar
        self._server.shutdown()

    async def end_background(self):
        await self._runner.cleanup()

    async def _websocket_handler(self, request):
        ws = web.WebSocketResponse()
        if not ws.can_prepare(request).ok:
            return self._NIP11_relay_info_route()

        await ws.prepare(request)

        # give the socket a unique id
        ws.id = self._ws_id
        self._ws_id += 1

        self._ws[ws.id] = {
            'subs': {},
            'ws': ws
        }

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await self._do_request(ws, msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print('ws connection closed with exception %s' %
                      ws.exception())

        del self._ws[ws.id]

        return ws

    async def _do_request(self, ws, req_str):
        # passed nothing? nothing to do
        if not req_str:
            return

        try:
            as_json = json.loads(req_str)
            err = None
            if not as_json:
                raise NostrNoticeException('No command received')
            cmd = as_json[0]
            if cmd not in Relay.VALID_CMDS:
                raise NostrNoticeException('unsupported command %s' % cmd)

            # a post of an event
            if cmd == 'EVENT':
                await self._do_event(as_json, ws)
            # register a subscription
            elif cmd == 'REQ':
                await self._do_sub(as_json, ws)
            elif cmd == 'CLOSE':
                await self._do_unsub(as_json, ws)

        except JSONDecodeError as je:
            err = ['NOTICE', 'unable to decode command string']
        except NostrNoticeException as ne:
            err = ['NOTICE', str(ne)]
        except NostrCommandException as nc:
            err = nc.get_data()


        await self._do_send(ws=ws,
                            data=err)

    async def _persist_events(self):
        async for job in self._write_queue:
            print(job)

    async def _do_event(self, req_json, ws):
        if len(req_json) <= 1:
            raise NostrNoticeException('EVENT command missing event data')
        evt = Event.from_JSON(req_json[1])
        # check event sig matches pub_key
        if not evt.is_valid():
            raise NostrCommandException(event_id=evt.id,
                                        success=False,
                                        message='invalid: signature validation failed')

        # pass evt through all AcceptReqHandlers, if any are not happy they'll raise
        # NostrCommandException otherwise we should be good to go
        for c_accept in self._accept_req:
            c_accept.accept_post(ws, evt)
        # if self._store:
        #     self._write_queue.put_nowait((ws,evt))

        try:
            saved = False
            if self._store:
                if isinstance(self._store, ARelayEventStoreInterface):
                    await self._store.add_event(evt)
                else:
                    self._store.add_event(evt)
                logging.debug('Relay::_do_event event sent to store %s ' % evt)
                saved = True
        except Exception as e:
            logging.debug('Relay::store event failed - %s' % e)

        # do the subs
        await self._check_subs(evt)

        if self._ack_events:
            raise NostrCommandException(event_id=evt.id,
                                        success=saved,
                                        message='')



    async def _check_subs(self, evt: Event):
        """

        :param evt:
        :return:
        """
        tasks = set()
        for socket_id in self._ws:
            for c_sub_id in self._ws[socket_id]['subs']:
                the_sub = self._ws[socket_id]['subs'][c_sub_id]
                # event passes sub filter
                if evt.test(the_sub['filter']):
                    n_task = asyncio.create_task(self._send_event(self._ws[socket_id]['ws'], c_sub_id, evt.event_data()))
                    tasks.add(n_task)
                    n_task.add_done_callback(tasks.discard)


    async def _do_sub(self, req_json, ws):
        logging.info('subscription requested - %s' % req_json)
        # get sub_id and filter fro the json
        if len(req_json) <= 1:
            raise NostrNoticeException('REQ command missing sub_id')
        sub_id = req_json[1]
        # if we don't get a filter default to {} rather than error?
        # did this because loquaz doesnt supply so assuming this is permited
        filter = {}
        if len(req_json) > 2:
            filter = req_json[2:]
            # raise NostrCommandException('REQ command missing filter')

        # this user already subscribed under same sub_id
        socket_id = ws.id
        if sub_id in self._ws[socket_id]['subs']:
            raise NostrNoticeException('REQ command for sub_id that already exists - %s' % sub_id)
        # this sub would put us over max for this socket
        sub_count = len(self._ws[socket_id]['subs'])
        if sub_count >= self._max_sub:
            raise NostrNoticeException('REQ new sub_id %s not allowed, already at max subs=%s' % (sub_id, self._max_sub))

        self._ws[socket_id]['subs'][sub_id] = {
            'id': sub_id,
            'filter': filter
        }

        logging.info('Relay::_do_sub subscription added %s (%s)' % (sub_id, filter))

        # get and send any stored events we have and send back
        evts = []
        if self._store:
            if isinstance(self._store, ARelayEventStoreInterface):
                evts = await self._store.get_filter(filter)
            else:
                evts = self._store.get_filter(filter)

        for c_evt in evts:
            await self._send_event(ws, sub_id, c_evt)

        # send EOSE event if enabled - unlikely it wouldn't be
        if self._nip15:
            await self._send_eose(ws, sub_id)

    async def _do_unsub(self, req_json, ws):
        logging.info('un-subscription requested')
        if len(req_json) <= 1:
            raise NostrCommandException('REQ command missing sub_id')

        # get sub_id from json
        sub_id = req_json[1]
        # user isn't subscribed anyhow, nothing to do
        socket_id = ws.id
        if sub_id not in self._ws[socket_id]['subs']:
            raise NostrCommandException('CLOSE command for sub_id that not subscribed to, nothing to do - %s' % sub_id)

        # remove the sub
        del self._ws[socket_id]['subs'][sub_id]
        # not actual exception but this will send notice back that sub_id has been closed, might be useful to client?
        raise NostrNoticeException('CLOSE command for sub_id %s - success' % sub_id)

    async def _do_send(self, ws: http_websocket, data):
        try:
            await ws.send_str(json.dumps(data))
        except Exception as e:
            logging.info('Relay::_do_send error: %s' % e)

    async def _send_event(self, ws: http_websocket, sub_id, evt):
        await self._do_send(ws=ws,
                            data=[
                                'EVENT',
                                sub_id,
                                evt
                            ])

    async def _send_eose(self, ws: http_websocket, sub_id):
        """
        NIP15 send end of stored events notice
        https://github.com/nostr-protocol/nips/blob/master/15.md
        """
        await self._do_send(ws=ws,
                            data=[
                                'EOSE', sub_id
                            ])

    def _NIP11_relay_info_route(self):
        """
        as https://github.com/nostr-protocol/nips/blob/master/11.md
        :return:
        """
        return web.Response(text=json.dumps(self._relay_information))

#    below are some routes that can be added to the monstr relay and give methods to access data via standard url in the
#    webbrowser. Useful for testing, maybe also for other things?
#    the can be added by doing relay.app.route('/route_url', callback=route_method(relay))


def event_route(r: Relay):
    """
        adds a route to access events by id for example:

            relay.app.route('/e', callback=route_method(relay))
            http://host:port/e?id=<event_id> will now return events
    """
    async def the_route(request: web.Request):
        id = None
        if 'id' in request.query:
            id = request.query['id']

        try:
            if id == '':
                raise ValueError('id field is required')
            elif not Event.is_event_id(id):
                raise ValueError('id: %s is not a valid event id' % id)
            else:
                ret = {}

                filter = {
                    'ids': id
                }

                if isinstance(r.store, ARelayEventStoreInterface):
                    evts = await r.store.get_filter(filter)
                else:
                    evts = r.store.get_filter(filter)

                if evts:
                    ret = evts[0]

        except ValueError as ve:
            ret = str(ve)

        if isinstance(ret, str):
            ret = web.Response(text=ret)
        else:
            ret = web.json_response(ret)

        return ret

    return the_route


def view_profile_route(r: Relay):
    """
    a simple profile view for what we have in the relay
    :param r:
    :return:
    """
    async def the_route(request: web.Request):

        pub_k = None
        if 'pub_k' in request.query:
            pub_k = request.query['pub_k']

        try:
            if pub_k is None:
                raise ValueError('pub_k field is required')
            k = Keys.get_key(pub_k)
            if k is None:
                raise ValueError('%s - doesn\'t look like a valid nostr key' % pub_k)

            filter = {
                'authors': [k.public_key_hex()],
                'kinds': [Event.KIND_META]
            }

            if isinstance(r.store, ARelayEventStoreInterface):
                evts = await r.store.get_filter(filter)
            else:
                evts = r.store.get_filter(filter)

            evts = Event.latest_events_only([Event.from_JSON(c_evt) for c_evt in evts],
                                            kind=Event.KIND_META)




            if evts:
                p_attrs = json.loads(evts[0].content)
                name = '-'
                if 'name' in p_attrs:
                    name = p_attrs['name']

                about = '-'
                if 'about' in p_attrs:
                    about = p_attrs['about']

                picture = ''
                if 'picture' in p_attrs:
                    picture = """
                        <img src='%s' />
                    """ % p_attrs['picture']

                ret = """
                    <HTML>
                        <b>%s</b></br>
                        Name: %s <br>
                        About: %s <br>
                        %s    
                    </HTML>'
                """ % (k.public_key_hex(),
                       name,
                       about,
                       picture)

            else:
                ret = '%s no meta held on relay' % k.public_key_hex()

        except ValueError as ve:
            ret = str(ve)
        except JSONDecodeError as je:
            ret = str(je)

        if isinstance(ret, str):
            ret = web.Response(text=ret,
                               content_type='text/html')
        else:
            ret = web.json_response(ret)

        return ret

    return the_route


def filter_route(r: Relay):
    """
        similar to the id route but more flexible with a small subset of
        monstr filter availabe as if doing a REQ to the relay directly

            relay.app.route('/req', callback=route_method(relay))
            http://host:port/req?kinds=0?authors=some_key
    """
    async def the_route(request: web.Request):
        def _get_param(name: str, mutiple=False, numeric=False):

            def _make_numeric(val):
                n_val = None
                try:
                    n_val = int(val)
                except Exception as e:
                    pass

                return n_val

            field_vals = None
            if name in request.query:
                r_val = request.query[name]
                if mutiple:
                    r_val = r_val.split(',')
                else:
                    r_val = [r_val]

                if numeric:
                    r_val = [_make_numeric(r_val) for r_val in r_val if _make_numeric(r_val) is not None]

                if r_val:
                    if mutiple:
                        field_vals = r_val
                    else:
                        field_vals = r_val[0]

            return field_vals

        limit = _get_param('limit', mutiple=False, numeric=True)
        if limit is None or limit > 100:
            limit = 100

        authors = _get_param('authors', mutiple=True, numeric=False)
        kinds = _get_param('kinds', mutiple=True, numeric=True)
        ids = _get_param('ids', mutiple=True, numeric=False)

        filter = {
            'limit': limit
        }
        if authors:
            filter['authors'] = authors
        if kinds:
            filter['kinds'] = kinds
        if ids:
            filter['ids'] = ids

        if isinstance(r.store, ARelayEventStoreInterface):
            evts = await r.store.get_filter(filter)
        else:
            evts = r.store.get_filter(filter)

        ret = None
        if evts:
            ret = {
                'events': evts
            }

        return web.json_response(ret)

    return the_route