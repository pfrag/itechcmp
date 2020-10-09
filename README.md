# itechcmp
Cost estimation for LPWAN-based IoT service deployments.

# Requirements
Python 3, no special requirements.

# Model information
This software receives information about the available deployment strategies,
service configuration, and other cost factors (e.g., compute infrastructure
costs) as a JSON-formatted input file. Below is an example of such a model:

```
"LoRaWAN-cloud-based": {
  "description": "LoRaWAN connectivity with a lightweight gateway. The LoRaWAN stack, edge monitors and aggregator monitor run on the cloud. 4G is used for the gateway backhaul.",
  "infrastructure": {
    "devicecost": 15,
    "gatewaycost": 200
  },
  "network": {
    "basecost": 0,
    "datacap": 0,
    "extracostperbyte": 0,
    "backhaulbasecost": 5,
    "backhaulcostperbyte": 0.00001,
    "backhauldatacap": 2000000
  },
  "deployment": {
    "gatewaydevice": "edge",
    "gatewaystack": "dedicated",
    "stackdevice": "cloud",
    "edgemonitor": "dedicated",
    "monitordevice": "cloud",
    "aggregatormonitor": "cloud"
  }
}
```

The above includes information about IoT device and gateway costs, connectivity
related costs, and the deployment configuration. The following parameters can
be configured:

- `gatewaydevice`: `edge` if the model includes the deployment and management
of a (LoRaWAN) gateway, `null` otherwise (e.g., for NB-IoT-based deployments).
- `gatewaystack`: `dedicated` if the network stack is deployed at a separate 
physical (e.g., a RPi) or virtual machine, `shared` if it is collocated with
the gateway hardware.
- `stackdevice`: `edge` if the network stack is deployed at an edge device,
`cloud` for a Cloud VM, `mec` for a MEC VM, `null` if there's no network
stack to manage (as in NB-IoT or LoRaWAN managed-stack models).
- `edgemonitor`: `dedicated` if the monitor (IoT service component) is installed
in a separate machine (physical or virtual), `shared` if it's collocated with
the gateway.
- `monitordevice`: `edge` device, `cloud` or `mec`, depending on where it 
should be deployed.
- `aggregatormonitor`: `edge` device, `cloud` or `mec`, depending on where
it should be deployed.

Please note that we assume a two-level monitoring hierarchy with the following
assumptions:

- The system is organized in regions.
- Each regions includes a number of IoT devices.
- There can be one or more gateways per region. This applies to LoRaWAN-based
scenarios. The additional gateways may serve for redundancy.
- There is one L0 monitor per region. The monitor can be deployed at the edge,
if the scenario allows it.
- There is a single L1 monitor, which receives data from L0 monitors.

# Usage
```
python3 itechcmp.py /path/to/settings/file {-a,-d}
```
Input parameters: 

- JSON-encoded file with information about the different deployment models 
and the application configuration.
- `-a`: Outputs the cumulative expenditure for each month
- `-d`: Outputs the amortized per device cost at the end of Y1 for increasing
numbers of end devices.

To plot the results:

```
gnuplot -e "cumexp='/path/to/cumulative/expenditure/file'" -e "perdevice='/path/to/perdevice/expenditure/file'" plot.gp
```

The input files should have been produced by prior calls to `itechcmp.py` 
with the appropriate flags.

