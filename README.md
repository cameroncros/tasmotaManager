# tasmotaManager
Tool for managing tasmota devices in bulk

- Can scan a network, and find tasmota devices
- Backup configuration - In bulk
- Restore configuration - In bulk, not heavily tested, use at own risk
- Console environment that allows sending console commands to all devices. See: https://tasmota.github.io/docs/Commands/#control for command information

## Commands

### Scan

    scan 192.168.1.0/24

Scan an address range, and detect all tasmota devices.

### Save

    save
    save devices.json

Save the results of a scan. 

### Load

    load
    load devices.json

Load the devices previously saved.

### Backup

    backup

Backup all devices. Should call `save` afterwards.

### Restore

    restore

Restore all devices.

### Commands

    cmd SetOption86 1
    SetOption86 1
    MqttUser

Execute a command on all tasmota devices found in the scan. cmd prefix is optional.

For a full list of commands, see: https://tasmota.github.io/docs/Commands/
