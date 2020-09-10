import json
import sys

# TODO: monthlygwopex, nbiot flat rate rebooking (probably not necessary if it's per device), different cost of SBC if it's a gw vs. if it's plain compute)
"""
Gateway and monitor deployment models (this applies to lora deployments)

For each region, there is one (or more, for redundancy) physical gateways (e.g. RPis). The gateway stack can be:
- Colocated with the gateway on the same machine (gatewaystack: shared, gatewaydevice: edge)
- On a separate machine (gatewaystack: dedicated), either physical (gatewaydevice: edge) or on a cloud/edge VM (gatewaydevice: cloud/mec).

The edge monitor can be:
- On the same machine as the gateway stack (edgemonitor: shared)
- On a dedicated machine (monitor: dedicated), either on a physical (monitordevice: edge) or virtual (monitordevice: cloud/mec) machine. If monitor: shared, monitordevice is ignored (where it's deployed depends on the value of gatewaydevice).

Note that even if there are multiple gateways in a region, there could be a single gw stack controlling them. For reasons of load balancing, this stack could be scaled horizontally/vertically to handle the workload.
"""

def installation_cost(settings, modelname):
  """Returns the installation cost for the given model.

  The installation cost is the one-off cost for the procurement and setup of devices and gateways.
  Depending on the deployment model, more edge devices may be necessary. If the gatewaydevice is
  "edge" and the deployment model is not "shared", for each region we need to add an edge device 
  for the monitor.
  """
  gateway_cost = 0
  device_cost = 0

  # load model
  if modelname not in settings["models"]:
    return None
  model = settings["models"][modelname]

  # for each region, place a number of gateways and install devices --ignore availability/redundancy aspects
  # device cost also includes one-off setup fees (e.g., SIM card procurement and activation. typical one-off sim costs: 2.5 EUR)
  gateway_cost = settings["topology"]["gatewaysperregion"]*settings["topology"]["regions"]*model["infrastructure"]["gatewaycost"]  
  device_cost = settings["topology"]["devicesperregion"]*settings["topology"]["regions"]*model["infrastructure"]["devicecost"]

  return gateway_cost + device_cost

def monthly_network_cost(settings, modelname):
  """Returns the monthly cost for network traffic. 

  This includes both the cost for the transmissions from devices to gateways/base stations and
  the "backhaul" cost, if any, for the gateway uplink.
  """
  # load model
  if modelname not in settings["models"]:
    return None

  model = settings["models"][modelname]

  # cost calculation:
  # - Get traffic per device per month: message frequency*payload size*seconds_in_a_month
  num_devices = settings["topology"]["devicesperregion"]*settings["topology"]["regions"]
  device_traffic = settings["application"]["messagefrequency"]*settings["application"]["payloadsize"]*3600*24*30
  total_traffic = device_traffic*num_devices

  if "flatrate" in model["network"] and model["network"]["flatrate"]:
    subscription_cost = 0
  elif "managedstack" in model["network"] and model["network"]["managedstack"]:
    # get number of devices and calculate subscription cost. this works as follows:
    # - there's a flat cost up to a max number of devices. this increases in a stepwise function
    # - if "openended": true, then the most expensive data plan comes with unlimited devices. otherwise, 
    # - if the number of devices exceeds the maximum, an new data plan needs to be bought
    D = sorted(model["network"]["managedstack"]["devices"])
    C = sorted(model["network"]["managedstack"]["monthlyfee"])

    # number of devices not yet covered by a plan
    remaining_devs = num_devices
    num_max_subscriptions = 0
    if not model["network"]["managedstack"]["openended"]:
      # may need to buy more. find how many "expensive" data plans we need. the remaining devices will be served by one of 
      # the cheaper options. if num_devices < max number of devs covered by highest data plan, no need to buy more.
      num_max_subscriptions = int(num_devices/D[len(D)-1]) # could be 0
      remaining_devs = num_devices % D[len(D)-1] # could be == num_devices
      #print("not open ended: ", num_max_subscriptions, remaining_devs)

    data_plan = -1
    # see how to cover the rest of the devices
    # if !openended, remaining_devs is always < than the max plan, so at some point the loop will break
    # otherwise, the loop may not break. this means that the #devs covered my the max data plan is smaller than
    # the number of devices, but since it's an open-ended model, the most expensive data plan offers unlimited dev coverage. 
    # the monthly fee is thus the price of the most expensive data plan.
    for i in range(0, len(D)):
      if int(remaining_devs/D[i]) == 0:
        data_plan = i
        break
    if data_plan == -1:
      extra_monthly_fee = C[len(C) - 1]
    else:
      extra_monthly_fee = C[data_plan]
    #print("extra fee: ", extra_monthly_fee)
    subscription_cost = num_max_subscriptions*C[len(D) - 1] + extra_monthly_fee
  else:
    # - Calculate base subscription cost: each device pays a monthly cost. Excess costs are computed after the aggregate cap is exceeded. 
    """
    num_subscriptions = 0
    if model["network"]["datacap"]:  
      num_subscriptions = int(total_traffic/(model["network"]["datacap"]*1000)) + 1

    subscription_cost = num_subscriptions*model["network"]["basecost"]
    """

    # - calculate total device subscription cost: num_devices * (base_cost + excess_cost)
    """  
    excess_cost_per_device = 0
    if device_traffic > model["network"]["datacap"]*1000:
      excess_cost_per_device = (device_traffic - model["network"]["datacap"]*1000)*model["network"]["extracostperbyte"]
    subscription_cost = (model["network"]["basecost"] + excess_cost_per_device)*settings["topology"]["devicesperregion"]*settings["topology"]["regions"]
    """
    excess_cost = 0
    if total_traffic > model["network"]["datacap"]*1000:
      excess_cost = (total_traffic - model["network"]["datacap"]*1000)*model["network"]["extracostperbyte"]
    subscription_cost = model["network"]["basecost"]*num_devices + excess_cost

  # - calculate backhaul cost: if a gateway is connected to the cloud over a metered connection, apply a similar approach
  # for the aggregate gateway traffic. Worst case: redundant gateways, each gateway forwards the traffic of all devs in the region
  excess_cost_per_gateway = 0
  gateway_traffic = device_traffic*settings["topology"]["devicesperregion"]
  if gateway_traffic > model["network"]["backhauldatacap"]*1000:
    excess_cost_per_gateway = (gateway_traffic - model["network"]["backhauldatacap"]*1000)*model["network"]["backhaulcostperbyte"]
  gateway_cost = (model["network"]["backhaulbasecost"] + excess_cost_per_gateway)*settings["topology"]["gatewaysperregion"]*settings["topology"]["regions"]

  return subscription_cost + gateway_cost

def compute_cost(settings, modelname):
  # The compute cost depends on the model features:
  # - edgemonitor: "edge"/"mec"/"cloud" (RPi, mec server, cloud server)
  # - aggregatormonitor: "edge"/"mec"/"cloud"
  # - gatewaystack: "shared"/"dedicated"/"none" (shared with edge monitor on the same device/VM, dedicated device/VM, or none if not applicable (e.g. for NB-IoT)
  #
  # Then, we calculate compute power we need per region. this consists in the following:
  # - running the gw stack (* num gateways) -- we assume one network server stack per region
  # - run the monitors: should be (workload/throughput)*node cost
  # then, we need compute power to centrally process the total device workload: (workload/throughput)*node cost
  # finally, we need to account for per node monthly opex (electricity, hw failures, etc.)

  # load model
  if modelname not in settings["models"]:
    return None

  model = settings["models"][modelname]

  # number of physical edge devices (SBCs, e.g. raspberries)--NB: gateway devices are accounter for in the installation cost
  # here, we will need to add more edge devices if the deployment model is not "shared"
  num_edge_devices = 0
  num_cloud_vms = 0
  num_cloud_vcpus = 0
  num_mec_vms = 0
  num_mec_vcpus = 0
  workload = settings["application"]["messagefrequency"] * settings["topology"]["devicesperregion"]

  # get placement strategy features
  if model["deployment"]["gatewaydevice"] is not None: 
    # there is a gateway to deploy. check on what type of machine it should be hosted.
    if model["deployment"]["gatewaystack"] == "dedicated":
      # host the gateway stack on a dedicated machine, so check the device type
      if model["deployment"]["stackdevice"] == "edge":
        # check how many devices we need to handle the workload
        num_edge_devices += workload/settings["compute"]["rpi"]["gatewaythroughput"]
      elif model["deployment"]["stackdevice"] == "cloud":
        num_cloud_vms += 1
        num_cloud_vcpus += workload/settings["compute"]["vcpu"]["gatewaythroughput"]
      elif model["deployment"]["stackdevice"] == "mec":
        num_mec_vms += 1
        num_mec_vcpus += workload/settings["compute"]["vcpu"]["gatewaythroughput"]
    else: 
      # Shared deployment model. Need to check if the monitor is colocated with the gateway stack 
      # If so, we need to check how many "all in one" devices (gw+stack+monitor) we need to deploy
      # to handle the load. if gateway device is None, nothing to do (e.g. NB-IoT)
      if model["deployment"]["edgemonitor"] is not "dedicated":
        # gw+stack+monitor on the same machine. one of the gateways needs to host everything. if the gateways are not enough, add more devices.
        # how many edge devices do we need? NOTE: We ignore the effect of duplicates due to >1 GWs per region, assuming that each NS instance is responsible for handling the traffic of at most 1 GW.
        devs_to_add =  workload/settings["compute"]["rpi"]["allinonethroughput"] - settings["topology"]["regions"]*settings["topology"]["gatewaysperregion"]
        if devs_to_add > 0:
          num_edge_devices += devs_to_add
      else:
        # here, gw+stack are on the same machine but the monitor is separate.
        # first, we check on how many machines the stack needs to be hosted.
        # NOTE: Again we ignore duplicate traffic/workload
        # NOTE: The monitor requirements are checked later
        devs_to_add =  workload/settings["compute"]["rpi"]["gatewaythroughput"] - settings["topology"]["regions"]*settings["topology"]["gatewaysperregion"]
        if devs_to_add > 0:
          num_edge_devices += devs_to_add

  # now check how many devices we need for the monitors
  if model["deployment"]["edgemonitor"] == "dedicated":
    if model["deployment"]["monitordevice"] == "edge":
      num_edge_devices += workload/settings["compute"]["rpi"]["throughput"]
    elif model["deployment"]["monitordevice"] == "cloud":
      num_cloud_vcpus += workload/settings["compute"]["vcpu"]["throughput"]
      num_cloud_vms += 1
    elif model["deployment"]["monitordevice"] == "mec":
      num_mec_vcpus += workload/settings["compute"]["vcpu"]["throughput"]
      num_mec_vms += 1

  # check the necessary resources for aggregator monitors
  fullworkload = workload*settings["topology"]["regions"]

  if model["deployment"]["aggregatormonitor"] == "edge":
    num_edge_devices += fullworkload/settings["compute"]["rpi"]["throughput"]
  elif model["deployment"]["aggregatormonitor"] == "cloud":
    num_cloud_vcpus += fullworkload/settings["compute"]["vcpu"]["throughput"]
    num_cloud_vms += 1
  elif model["deployment"]["aggregatormonitor"] == "mec":
    num_mec_vcpus += fullworkload/settings["compute"]["vcpu"]["throughput"]
    num_mec_vms += 1

  if num_edge_devices > 0:
    num_edge_devices = int(num_edge_devices) + 1
  if num_cloud_vcpus > 0:
    num_cloud_vcpus = int(num_cloud_vcpus) + 1
  if num_mec_vcpus > 0:
    num_mec_vcpus = int(num_mec_vcpus) + 1

  # Now calculate costs. We return two values:
  # - Installation cost
  # - Monthly cost. Here, we need to account for *all* gw devices, i.e., not only the ones that we counted here)
  setup_cost = num_edge_devices*model["infrastructure"]["gatewaycost"]
  monthly_cost = (num_edge_devices + settings["topology"]["gatewaysperregion"]*settings["topology"]["regions"]) * settings["compute"]["rpi"]["monthlyextraopex"] + settings["computecosts"]["cloud"]["costpercpu"]*num_cloud_vcpus + settings["computecosts"]["mec"]["costpercpu"]*num_mec_vcpus
  return setup_cost, monthly_cost

def get_setup_cost(settings, model):
  return installation_cost(settings, model) + compute_cost(settings, model)[0]

def get_monthly_cost(settings, model):
  return monthly_network_cost(settings, model) + compute_cost(settings, model)[1]

def compare_all(settings):
  # calculate setup costs for each model
  aggregate_cost = {}
  for model in settings["models"].keys():
    aggregate_cost[model] = get_setup_cost(settings, model)

  # print labels
  print("month", end="\t")
  for model in settings["models"].keys():
    print(model, end="\t")
  print()

  for month in range(0, 37):    
    #print(month, aggregate_cost_lora, aggregate_cost_lora_cloud, aggregate_cost_nbiot, aggregate_cost_nbiot_mec)
    #print(month, lora, lora_cloud, nbiot_monthly, nbiot_flat)
    print(month, end="\t")
    for model in settings["models"].keys():
      print(int(aggregate_cost[model]), end="\t")
      aggregate_cost[model] += get_monthly_cost(settings, model)
    print()
  print()

def daily_cost_vs_devices(settings, month, nregions):
  """Calculate amortized daily cost over the first year for increasing numbers of devices.
  """

  # print labels
  print("devices", end="\t")
  for model in settings["models"].keys():
    print(model, end="\t")
  print()

  for n in range(100, 2001, 100):
  #for n in range(9900, 10001, 100):
    settings["topology"]["regions"] = nregions
    settings["topology"]["devicesperregion"] = n/nregions
    print(n, end="\t")
    for model in settings["models"].keys():
      cost = (get_setup_cost(settings, model) + month*get_monthly_cost(settings, model))/(month*30)
      print(int(cost), end="\t")
    print()
    
if __name__ == "__main__":
  # load settings
  with open(sys.argv[1]) as f:
    settings = json.load(f)
  daily_cost_vs_devices(settings, 36, 10)
  #compare_all(settings)

