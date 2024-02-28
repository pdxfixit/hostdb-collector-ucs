import copy
import datetime
import json
import logging
import os
import requests
import signal
import sys
import urllib3
import yaml
from contextlib import contextmanager
from ucsmsdk.ucsexception import UcsException
from ucsmsdk.ucshandle import UcsHandle
from ucsmsdk.utils import inventory
from urllib.error import URLError

# disable warnings when SSL is not being verified
urllib3.disable_warnings()


# stuff to enable timeout
class TimeoutException(Exception): pass


@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Terminated")

    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)


#
# create logger
#
logger = logging.getLogger("hostdb-collector-ucs")
logger.setLevel(logging.DEBUG)

# create console handler to print to screen
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter and add it to the handler
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

# add the handler to the logger
logger.addHandler(ch)

#
# load default configuration from file
#
logger.info("reading default config from file")

with open("config.yaml", "r") as yamlfile:
    cfg = yaml.safe_load(yamlfile)

#
# load config from env vars
#
logger.info("reading config from environment")

# collector
if "HOSTDB_COLLECTOR_UCS_COLLECTOR_DEBUG" in os.environ:
    if os.environ["HOSTDB_COLLECTOR_UCS_COLLECTOR_DEBUG"].lower() in ['true',
                                                                      '1']:
        cfg["collector"]["debug"] = True
    else:
        cfg["collector"]["debug"] = False

if "HOSTDB_COLLECTOR_UCS_COLLECTOR_SAMPLE_DATA" in os.environ:
    if os.environ["HOSTDB_COLLECTOR_UCS_COLLECTOR_SAMPLE_DATA"].lower() in [
        'true', '1']:
        cfg["collector"]["sample_data"] = True
    else:
        cfg["collector"]["sample_data"] = False

if "HOSTDB_COLLECTOR_UCS_COLLECTOR_SAMPLE_DATA_PATH" in os.environ:
    cfg["collector"]["sample_data_path"] = os.environ[
        "HOSTDB_COLLECTOR_UCS_COLLECTOR_SAMPLE_DATA_PATH"]

# hostdb
if "HOSTDB_COLLECTOR_UCS_HOSTDB_HOST" in os.environ:
    cfg["hostdb"]["host"] = os.environ["HOSTDB_COLLECTOR_UCS_HOSTDB_HOST"]

if "HOSTDB_COLLECTOR_UCS_HOSTDB_PASS" in os.environ:
    cfg["hostdb"]["pass"] = os.environ["HOSTDB_COLLECTOR_UCS_HOSTDB_PASS"]

if "HOSTDB_COLLECTOR_UCS_HOSTDB_USER" in os.environ:
    cfg["hostdb"]["user"] = os.environ["HOSTDB_COLLECTOR_UCS_HOSTDB_USER"]

# timeout
if "HOSTDB_COLLECTOR_UCS_TIMEOUT" in os.environ:
    cfg["timeout"] = os.environ["HOSTDB_COLLECTOR_UCS_TIMEOUT"]
else:
    cfg["timeout"] = 1200

# ucs
if "HOSTDB_COLLECTOR_UCS_UCS_HOSTS" in os.environ:
    # split by commas, stripped of whitespace
    cfg["ucs"]["hosts"] = [e.strip() for e in
                           os.environ["HOSTDB_COLLECTOR_UCS_UCS_HOSTS"].split(
                               ",")]

if "HOSTDB_COLLECTOR_UCS_UCS_PASS" in os.environ:
    cfg["ucs"]["pass"] = os.environ["HOSTDB_COLLECTOR_UCS_UCS_PASS"]

if "HOSTDB_COLLECTOR_UCS_UCS_USER" in os.environ:
    cfg["ucs"]["user"] = os.environ["HOSTDB_COLLECTOR_UCS_UCS_USER"]

# if debug is on, output the redacted config
if cfg["collector"]["debug"]:
    cfgOutput = copy.deepcopy(cfg)
    cfgOutput["hostdb"]["pass"] = "*****" + cfg["hostdb"]["pass"][-3:]
    cfgOutput["ucs"]["pass"] = "*****" + cfg["ucs"]["pass"][-3:]
    logger.debug("{}".format(cfgOutput))

#
# for each host in config
#
overallSuccess = True
try:
    with time_limit(cfg["timeout"]):
        for host in cfg["ucs"]["hosts"]:
            if host == "":
                continue

            handle = UcsHandle(host, cfg["ucs"]["user"], cfg["ucs"]["pass"], "443")
            try:
                logger.info("accessing: {user} @ {host}".format(user=cfg["ucs"]["user"],
                                                                host=host))
                handle.login()
            except UcsException as err:
                logger.error("Exception: {}".format(err))
                overallSuccess = False
                continue
            except URLError as err:
                logger.error("{}".format(err))
                overallSuccess = False
                continue

            #
            # get UCS resources
            #
            items = []
            try:
                if cfg["collector"]["debug"]:
                    logger.info("getting inventory...")
                items = inventory.get_inventory(handle)[host]
                if cfg["collector"]["debug"]:
                    logger.debug("{}".format(items))
            except Exception as err:
                logger.error("Exception: {}".format(err))
                overallSuccess = False
                continue

            # cpu,disks,memory,psu,pci,vic,vNICs,vHBAs,storage,fabric_interconnect
            for r in inventory.inventory_spec.keys():
                logger.info("found {len} {type}".format(len=len(items[r]),
                                                        type=
                                                        inventory.inventory_spec[r][
                                                            "class_id"]))

                #
                # create HostDB records
                #
                hostdbRecords = []
                for e in items[r]:
                    # add e as data in a new HostDB record
                    record = {
                        "data": e,
                    }

                    if r == "fabric_interconnect":
                        if e["oob_if_ip"]:
                            record["ip"] = e["oob_if_ip"]

                    hostdbRecords.append(record)

                #
                # create a HostDB recordset
                #
                recordType = "ucs-{}".format(r.lower().rstrip("s"))  # ucs-vhba
                hostdbRecordSet = {
                    "type": recordType,
                    "committer": "hostdb-collector-ucs",
                    "context": {
                        "ucs_url": host,  # ucsfi.pdxfixit.com
                    },
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "records": hostdbRecords,
                }

                if cfg["collector"]["debug"]:
                    logger.debug("{}".format(hostdbRecordSet))

                #
                # save the data somewhere
                #
                if cfg["collector"]["sample_data"]:
                    #
                    # create sample-data file
                    #
                    filePath = "{path}/{host}_{type}.json".format(
                        path=cfg["collector"]["sample_data_path"],
                        host=host, type=recordType)

                    logger.info("writing to {}".format(filePath))

                    f = open(filePath, "w")
                    f.write(json.dumps(hostdbRecordSet))
                    f.close()

                    logger.info("saved data to {}".format(filePath))
                else:
                    #
                    # post to hostdb
                    #
                    url = "{host}/v0/records/?ucs_url={ucs_url}&type={type}".format(
                        host=cfg["hostdb"]["host"], ucs_url=host, type=recordType)

                    if cfg["collector"]["debug"]:
                        logger.debug("posting to {}".format(url))

                    try:
                        response = requests.post(url, {}, hostdbRecordSet, verify=False,
                                                 auth=(cfg["hostdb"]["user"],
                                                       cfg["hostdb"]["pass"]))
                    except URLError as err:
                        logger.error("{}".format(err))
                        overallSuccess = False
                        continue

                    logger.info("sent data to {}".format(url))

                    if cfg["collector"]["debug"]:
                        logger.debug("{}".format(response))

                    if response.status_code != 200:
                        logger.error(
                            "hostdb returned {}".format(response.status_code))
                        overallSuccess = False

            #
            # logout
            #
            logger.info("logging out of {}".format(host))
            handle.logout()
except TimeoutException as e:
    print("Ran too long ... Terminated!")

#
# all done
#
logger.info("ALL DONE!")
if overallSuccess:
    sys.exit(0)
else:
    sys.exit(1)
