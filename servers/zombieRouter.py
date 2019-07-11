from _thread import start_new_thread, allocate_lock
from network import LoRa
import socket
from loramesh import Loramesh
from zombiegram import *
import logging
import time
import machine
from dropqueue import DropQueue
from volatileconfiguration import VolatileConfiguration as Config
import urequests
import gc

class ZombieRouterException(Exception):
    pass


class ZombieRouterInvalidAckCache(ZombieRouterException):
    pass


class ZombieRouter:

    # Ports are technically not used, LoRa listens to all incoming traffic on the interface
    # https://forum.pycom.io/topic/4077/a-few-questions-about-the-lora-mesh/2
    __device_source_id = bytes_to_int(machine.unique_id()) & 0xFFFFFFFF
    __port = 1337
    __max_transmissions_per_burst = 10

    def __init__(self, lora_object):
        self._started = False
        self._stop_called = False
        if lora_object:
            self._lora = lora_object
        else:
            self._lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868, bandwidth=LoRa.BW_125KHZ, sf=7)
        self._lora_mesh = None
        self._socket = None
        self._neighbor_sequences = {}
        self._package_acks = {}
        self._zombiegram_queue = []
        self._zombiegram_queue_lock = allocate_lock()

    def start(self):
        """Starts the ZombieRouter LoRa mechanism on a separate thread
        """
        if not self._started:
            self._lora_mesh = Loramesh(lora=self._lora)
            self._lora_mesh.mesh.rx_cb(self._process_package)
            self._socket = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
            self._socket.bind(ZombieRouter.__port)
            self._started = True
            self._stop_called = False
            start_new_thread(self._lora_zombiegram_processor, ())

    def stop(self):
        logging.getLogger("zombierouter").info("Zombierouter stop issued. Please wait LoRa routing threads to stop. (10sec)")
        self._stop_called = True
        self._lora_mesh.mesh.rx_cb(self._process_package_dummy)

    def is_network_ready(self):
        """Retrieve whether the network is ready for packet transmissions
        
        :return: True or false representing ready and not-ready respectively
        :rtype: bool
        """
        started = self._started
        connected = self._lora_mesh.is_connected() if started else False
        has_neighbors = True if connected and self._lora_mesh.neighbors() else False
        return has_neighbors

    def retransmission_count(self):
        count = 0
        for source, rt_cache in self._package_acks.items():
            count += rt_cache.retransmission_count()
        return count
    
    def get_neighbors(self):
        neighbor_ids = []
        if self._started and self._lora_mesh.neighbors():
            count = 0
            for neighbor in self._lora_mesh.neighbors():
                neighbor_ids.append(neighbor[0] & 0xFFFFFFFF)
        return neighbor_ids

    def _handle_retransmissions(self):
        # Retrieve all unfinished packages
        package_collection = []
        total_wipes = 0
        
        neighbor_count = len(self._lora_mesh.neighbors()) if self._lora_mesh.neighbors() else 0
        for source, rt_cache in self._package_acks.items():
            source_collection, wipes = rt_cache.remove_completed_packages(neighbor_count)
            package_collection += source_collection
            total_wipes += wipes
        if neighbor_count == 0 and total_wipes > 0:
            logging.getLogger("zombierouter").debug("Current neighbor count is 0, all retransmission caches were wiped.")
            return

        # Sort by priorty
        package_collection.sort(key=lambda x: x.priority, reverse=True) # Highest priority = highest value -> Reverse required
        
        # Retransmit
        for package in package_collection[0:10]:
            self.forward_zombiegram(package, False)
            logging.getLogger("zombierouter").debug("Retransmitting package from source_id [{}] to all neighbors.".format(package.source_id))

    def _lora_zombiegram_processor(self):
        # Start up Meshing
        while True:
            time.sleep(2) # Short sleep since this is only a mesh boot
            if not self._lora_mesh.is_connected():
                continue
            break

        # A mesh has been initialised or we are connected to one
        ip = self._lora_mesh.ip()
        while not self._stop_called:
            new_ip = self._lora_mesh.ip() # Triggers internal update (Pycom weird implementation detail)
            if ip != new_ip:
                logging.getLogger("zombieserver").info("LoRa mesh interface IP changed from [{}] to [{}]".format(ip, new_ip))
                ip = new_ip

            # Handle queued items
            if self.is_network_ready() and self._zombiegram_queue:
                with self._zombiegram_queue_lock:
                    for queue_item in self._zombiegram_queue:
                        self.send_zombiegram(queue_item[0], *(queue_item[1]))
                    logging.getLogger("zombierouter").info("A total of [{}] queued zombiegrams were sent out.".format(len(self._zombiegram_queue)))
                    del self._zombiegram_queue[:]

            # Retransmission logic
            self._handle_retransmissions()

            time.sleep(10) # Longer sleep

        self._lora_mesh.mesh.deinit()
        self._socket.close()
        self._started = False
        with self._zombiegram_queue_lock:
            del self._zombiegram_queue[:]
        logging.getLogger("zombierouter").info("Zombierouter thread stopped. Router is now inactive.")        

    def _handle_gateway_propagation(self, zombiegram):
        gateway_hooks = []
        if Config.get("gateway_webhook_1", None): gateway_hooks.append(Config.get("gateway_webhook_1"))
        if Config.get("gateway_webhook_2", None): gateway_hooks.append(Config.get("gateway_webhook_2"))
        if Config.get("gateway_webhook_3", None): gateway_hooks.append(Config.get("gateway_webhook_3"))

        for hook in gateway_hooks:
            try:
                urequests.post(hook, json=zombiegram.serialize_to_dict(Config.get("device_trust_key", None)))
                logging.getLogger("zombierouter").debug("Propagated incoming zombiegram to external hook [{}]".format(hook))
            except Exception as e:
                logging.getLogger("zombierouter").debug("External hook [{}] could not be contacted | Reason [{}]".format(hook, str(e)))

    def _process_package_dummy(self):
        pass

    def _process_package(self):
        # We can assume package never are bigger than 64 bytes due to the Zombiegram constraints
        # In case we do receive some malformed/unexpected package we need to filter it out
        while True:
            rcv_data, rcv_addr = self._socket.recvfrom(Zombiegram.get_max_package_size())
            if len(rcv_data) == 0: # Mandatory check
                break

            rcv_addr = rcv_addr[0]
            logging.getLogger("zombieserver").debug("LoRa interface detected incoming message from IP [{}]".format(rcv_addr))
            try:
                zg = Zombiegram.from_package(rcv_data)
                logging.getLogger("zombieserver").debug(zg)

                # Check if this message is not one of our own returning
                if zg.source_id == bytes_to_int(ZombieRouter.__device_source_id):
                    logging.getLogger("zombieserver").debug("Incoming message is our own, ignoring.")
                    continue

                # Check if we already encountered this neighbor
                if not zg.source_id in self._neighbor_sequences:
                    self._neighbor_sequences[zg.source_id] = DropQueue(10)

                # Check if we already encountered this message
                zombiegram_needs_to_be_acknowledged = True
                zombiegram_needs_gateway_forwarding = True
                if zg.seq_num not in self._neighbor_sequences[zg.source_id]:
                    # This zombiegram has not been encountered before, acknowledge it and process its contents and forward if needed
                    for payload in zg.get_payloads():
                        if isinstance(payload, AcknowledgePayload):
                            zombiegram_needs_to_be_acknowledged = False
                            zombiegram_needs_gateway_forwarding = False
                            try:
                                self._package_acks[payload.source_id].add_ack_from(zg.source_id, payload.seq_num)
                            except: pass # We can ignore this; a cache miss can happen when enough acks are already received and the given seq_num is removed by _handle_retransmissions()
                            logging.getLogger("zombierouter").debug("Received acknowledgement from [{}] for a sent zombiegram from source_id [{}] with seq_num [{}]".format(zg.source_id, payload.source_id, payload.seq_num))
                        if isinstance(payload, NetworkChange):
                            Config.set("device_trust_key", None, True, True)
                            Config.save_configuration_to_datastore("global")
                            zombiegram_needs_gateway_forwarding = False

                    # We only forward non-ack zombiegrams
                    if zombiegram_needs_to_be_acknowledged:
                        self.forward_zombiegram(zg)

                    # Gateway forwarding
                    if Config.get("device_is_gateway", False) and zombiegram_needs_gateway_forwarding:
                        self._handle_gateway_propagation(zg)

                    # Add to seen queue
                    self._neighbor_sequences[zg.source_id].append(zg.seq_num)
                else:
                    logging.getLogger("zombierouter").debug("Zombiegram from [{}] with seq_num[{}] was already seen by this device, ignoring.".format(zg.source_id, zg.seq_num))

                # An Acknowledgement is needed in any case since our ack might have gotten lost or this is the first time we see this zombiegram
                if zombiegram_needs_to_be_acknowledged:
                    self._send_acknowledgement(source=zg.source_id, seq=zg.seq_num, to=rcv_addr)
                
            except Exception as e:
                logging.getLogger("zombieserver").warning("LoRa interface received unknown/malformed data | Exception [{}] | Data [{}]".format(str(e), rcv_data))
        
    def _create_zombiegram_header(self, priority):
        seq = 0
        try:
            seq = (Config.get("lora_seq_num", 0) + 1) % 256
        except:
            pass
        if not isinstance(priority, int) or priority < 0 or priority > 3:
            priority = 1
        tampered = Config.get("lora_tampered_flag", False)
        maintenance = Config.get("lora_maintenance_flag", False)
        zg = Zombiegram(source_id=ZombieRouter.__device_source_id, seq_num=seq, tampered_flag=tampered, maintenance_flag=maintenance, priority_flag=priority)
        Config.set("lora_seq_num", seq, False)
        return zg

    def _create_zombiegram_with_payloads(self, priority, *payloads):
        zg = self._create_zombiegram_header(priority)
        for payload in payloads:
            zg.add_payload(payload)
        zg.sign_package(Config.get("device_trust_key", None))
        return zg
        
    def _send_zombiegram_to(self, zombiegram, address, add_to_retransmission_cache=False):
        try:
            self._socket.sendto(zombiegram.get_bytestring_representation(), (address, ZombieRouter.__port)) # MULTICAST_LINK_ALL = All neighbors
        except Exception as e: # Socket only throws OSError (µpython implementation specifics), we want to capture everything here
            logging.getLogger("zombierouter").error("Sending data over LoRa network failed even though setup completed! Data will be lost. | Addressed to [{}] | Reason [{}]".format(address, str(e)))
            return

        # Retransmission queue logic
        if add_to_retransmission_cache:
            try:
                if zombiegram.source_id not in self._package_acks:
                    self._package_acks[zombiegram.source_id] = ZombieRouter.RetransmissionCache()
                own_message = bytes_to_int(ZombieRouter.__device_source_id) == zombiegram.source_id
                self._package_acks[zombiegram.source_id].add_package(zombiegram, own_message)
                logging.getLogger("zombierouter").debug("Zombiegram from [{}] with seq_num [{}] added to the retransmission cache.".format(zombiegram.source_id, zombiegram.seq_num))
                if own_message and Config.get("device_is_gateway", False):
                    self._handle_gateway_propagation(zombiegram)
            except ZombieRouterInvalidAckCache as e:
                logging.getLogger("zombierouter").warning("Adding zombiegram from [{}] with seq_num [{}] to retransmission cache failed! | Reason [{}]".format(zombiegram.source_id, zombiegram.seq_num, str(e)))

    def _send_acknowledgement(self, source, seq, to):
        ack = AcknowledgePayload(source, seq)
        zg = self._create_zombiegram_with_payloads(1, ack)
        self._send_zombiegram_to(zg, to, False)
        logging.getLogger("zombierouter").debug("Acknowledgement for seq_num [{}] sent to [{}]".format(seq, to))

    def forward_zombiegram(self, zombiegram, add_to_retransmission_cache=True):
        """Send a Zombiegram object over the LoRa network to all neighbors
        Used for forwarding zombiegrams or sending selfcrafted zombiegrams
        
        :param Zombiegram zombiegram: object containing a valid zombiegram
        :param bool add_to_retransmission_cache: When set to false, the package will not be added to the retransmission cache
        :raises ZombieRouterException: When a non-zombiegram object is given
        :raises ZombieRouterException: When the zombiegram is not signed
        :raises ZombieRouterException: When the LoRa mesh is not yet available
        """
        if not isinstance(zombiegram, Zombiegram):
            raise ZombieRouterException("Non-Zombiegram package was given. Only Zombiegrams can be send over the network at this time. | Given type [{}]".format(type(zombiegram)))
        if not zombiegram.is_signed():
            raise ZombieRouterException("Zombiegram has not been signed, please sign the zombiegram before sending it over the network.")
        if not self.is_network_ready():
            raise ZombieRouterException("LoRa zombie mesh is not yet available.")
        self._send_zombiegram_to(zombiegram, self._lora_mesh.MULTICAST_LINK_ALL, add_to_retransmission_cache)

    def send_zombiegram(self, priority, *payloads):
        self._send_zombiegram_to(self._create_zombiegram_with_payloads(priority, *payloads), self._lora_mesh.MULTICAST_LINK_ALL, True)

    def queue_zombiegram(self, priority, *payloads):
        # zg = self._create_zombiegram_with_payloads(priority, *payloads)
        with self._zombiegram_queue_lock:        
            self._zombiegram_queue.append((priority, payloads))
        logging.getLogger("zombierouter").info("Payloads were queued with a priority of [{}]".format(priority))

    class RetransmissionCache:
        """Keep a cache of sent or forwarded zombiegrams
        This class manages their respective unique acknowledgement counts

        :note: This cache is specific to a device (i.e. source_id); keeping a global cache will result in ZombieRouterInvalidAckCache exceptions due to cache collisions
        """
        
        __own_message_propagation_value = 0.5
        __neighbor_message_propagation_value = 0.3
        __priority_propagation_values = [0.7, 0.8, 0.9, 1] # low, normal, high and urgent respectively

        def __init__(self):
            # seq_num => [received ack count, [list of acked destionation ids], Zombiegram, own message (bool)]
            self._cache = {}

        def retransmission_count(self):
            return len(self._cache)

        def add_package(self, send_zombiegram, own_message):
            """Add a zombiegram to the retransmission cache
            
            :param send_zombiegram: Sent out zombiegram
            :type send_zombiegram: zombiegram   
            :raises ZombieRouterInvalidAckCache: When the seq_num is already known to the system (i.e. we have a collision)
            """
            if send_zombiegram.seq_num in self._cache:
                raise ZombieRouterInvalidAckCache("Cache item with seq_num [{}] causes a collision. Are items not being removed? Did we send 255 LoRa messages in short time?".format(send_zombiegram.seq_num))
            self._cache[send_zombiegram.seq_num] = [0, [], send_zombiegram, own_message]

        def add_ack_from(self, source_id, seq_num):
            """Indicate an acknowledgement happened from a certain source
            
            :param int source_id: Source ID as converted by the Zombiegram class
            :param int seq_num: seq_num that was acknowledged
            :raises ZombieRouterInvalidAckCache: When the cache has no notion of the given seq_num (i.e. no add_package() happened explicitly before)
            """
            if not self._cache.get(seq_num):
                raise ZombieRouterInvalidAckCache("Cache item with seq_num [{}] does not exist.".format(seq_num))
            if source_id not in self._cache[seq_num][1]:
                self._cache[seq_num][1].append(source_id)
                self._cache[seq_num][0] += 1

        def get_ack_count(self, seq_num):
            """Retrieve the ack count of a certain seq_num
            
            :param int seq_num: seq_num we want the count of
            :raises ZombieRouterInvalidAckCache: When the seq_num is not known to the cache
            :return: Ack count
            :rtype: int
            """
            if not self._cache.get(seq_num):
                raise ZombieRouterInvalidAckCache("Cache item with seq_num [{}] does not exist.".format(seq_num))
            return self._cache[seq_num][0]

        def remove_completed_packages(self, current_neighbor_count):
            """Remove all packages from the cache that hit or exceed the calculated treshold
            
            :param int current_neighbor_count: Current neighbor count, setting this value to 0 wipes the cache
            :return: List of all packages that do not meet the given treshold
            :rtype: list
            """
            if current_neighbor_count == 0:
                wipes = len(self._cache)
                self._cache = {}
                return [], wipes

            own_message_treshold = (current_neighbor_count * ZombieRouter.RetransmissionCache.__own_message_propagation_value) # Value without priority
            neighbor_message_treshold = (current_neighbor_count * ZombieRouter.RetransmissionCache.__neighbor_message_propagation_value) if current_neighbor_count > 1 else 0 # Value without priority

            retry_zombiegrams = []
            wipes = 0
            for seq_num, data in self._cache.items():
                treshold = (own_message_treshold if data[3] else neighbor_message_treshold) * ZombieRouter.RetransmissionCache.__priority_propagation_values[data[2].priority]
                if data[0] >= treshold:
                    self._cache.pop(seq_num, None) # Key should exist, silently ignore it with "None" if it doesn't for some reason
                    wipes += 1
                else:
                    retry_zombiegrams.append(data[2])
            return retry_zombiegrams, wipes
 