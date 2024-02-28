# HostDB Collector for UCS Manager

Queries the UCS Manager REST API, to inventory all available objects, and sends that data to HostDB.

## Getting Started

### Prerequisites

This collector requires a few things to operate:

* Docker (or other container runtime)
* An instance of UCS Manager to query
* A HostDB instance to write to (optional)

The application itself has the following python wheel dependencies:

* [PyYAML](https://pypi.org/project/PyYAML/)
* [requests](https://pypi.org/project/requests/)
* [ucsmsdk](https://pypi.org/project/ucsmsdk/)

### Running

The collector is written in Python, and is designed to be run from a container. The following environment variables are necessary for operation:

* `HOSTDB_COLLECTOR_UCS_HOSTDB_PASS` -- the password for HostDB writing (can be omitted if generating sample data)
* `HOSTDB_COLLECTOR_UCS_UCS_PASS` -- the password for accessing the UCS instance

```shell script
$ docker run -it --rm -e HOSTDB_COLLECTOR_UCS_HOSTDB_PASS='sekretpassword' -e HOSTDB_COLLECTOR_UCS_UCS_PASS='soopersekretpassword' registry.pdxfixit.com/hostdb-collector-ucs
```

#### Long running jobs

Sometimes the collector gets stuck, and needs to be restarted.
If the collector runs for longer than 2h, it will be terminated.
The timeout duration can be changed with the environment variable `HOSTDB_COLLECTOR_UCS_TIMEOUT`.
The default is `1200`.

### Sample Data

In addition, the variable `HOSTDB_COLLECTOR_UCS_COLLECTOR_SAMPLE_DATA` to true, and the collector will output all collected data to files (configurable via `HOSTDB_COLLECTOR_UCS_COLLECTOR_SAMPLE_DATA_PATH`), instead of attempting to HTTP POST it to HostDB.

One can simply run:

```shell script
$ make sample_data
```

Or manually:

```shell script
$ docker run -it --rm -v `pwd`/sample-data:/sample-data -e HOSTDB_COLLECTOR_UCS_COLLECTOR_SAMPLE_DATA=true -e HOSTDB_COLLECTOR_UCS_UCS_PASS='soopersekretpassword' registry.pdxfixit.com/hostdb-collector-ucs
```

## Running tests

Somebody should probably write some tests.

## Deployment

The collector ran from a container on a regular schedule.

https://builds.pdxfixit.com/gh/hostdb-collector-ucs

## Debugging

Set the environment variable `HOSTDB_COLLECTOR_UCS_COLLECTOR_DEBUG` to true, and the collector will output additional detail.

## Built With

Build will run create a container, and upload that container image to the registry for use during scheduled runs.

## Authors & Support

- Email: info@pdxfixit.com

## See Also

- [ucsmsdk](https://github.com/CiscoUcs/ucsmsdk)
