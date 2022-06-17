import asyncio
import base64
import io
import json
from argparse import ArgumentParser
from ipaddress import IPv4Network
from typing import Any, Tuple, List, Optional
from urllib.parse import urlencode

import aiohttp as aiohttp
import requests


class Device:
    def __init__(self, address, data):
        self.address = str(address)
        self.data = data

    def __eq__(self, other):
        return self.address == other.address

    async def send_command(self, command: str) -> Tuple[str, Any]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(5)) as session:
            args = {'cmnd': command}
            url = f'http://{self.address}:80/cm?{urlencode(args)}'
            try:
                resp = await session.request('GET', url=url)
                json = await resp.json()
                return self.address, json
            except Exception as e:
                return self.address, None

    async def backup(self) -> bool:

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(5)) as session:
            url = f'http://{self.address}:80/dl'
            try:
                resp = await session.request('GET', url=url)
                config = await resp.read()
                self.data = {'config': base64.b64encode(config).decode('utf-8')}
                return True
            except Exception as e:
                return False

    async def restore(self) -> bool:
        if not self.data['config']:
            return False
        try:
            # Can't work out how to do this properly with aiohttp, just use requests
            # Sets internal tasmota state
            url = f'http://{self.address}:80/rs?'
            requests.get(url)

            # Upload the config
            url = f'http://{self.address}:80/u2'
            f = io.BytesIO(base64.b64decode(self.data['config']))
            response = requests.post(url, files={'u2': f})
            if response and b"Successful" in response.content:
                return True
            print(response)
            print(response.content)
            return False
        except Exception as e:
            print(e)
            return False

    def get_config(self):
        return self.data


async def scan_address(address) -> Optional[Device]:
    device = Device(address, {})
    _, response = await device.send_command('Status 2')
    if response is not None and 'tasmota' in response['StatusFWR']['Version']:
        print(f'Found device: {address}')
        return device
    return None


async def scan_devices(network: str) -> List[Optional[Device]]:
    net_address = IPv4Network(network)
    scans = []
    for address in net_address:
        scans.append(scan_address(address))
    results = await asyncio.gather(*scans)
    return results


def load_devices(config_file) -> List[Device]:
    devices = []
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            for address in config:
                devices.append(Device(address, data=config[address]))
    except:
        pass
    return devices


def save_devices(config_file: str, devices: List[Device]):
    config = {}
    for device in devices:
        config[str(device.address)] = device.get_config()
    with open(config_file, 'w') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


async def repl(devices: List[Device]):
    while True:
        command = input('> ')
        results = []
        for device in devices:
            results.append(device.send_command(command))
        results = await asyncio.gather(*results)
        for result in results:
            print(f"{result[0]}: {result[1]}")
        print(f"\n")


async def restore(devices: List[Device]):
    scans = []
    for device in devices:
        scans.append(device.restore())
    results = await asyncio.gather(*scans)
    print(results)


async def backup(devices: List[Device]):
    print("Backing up:")
    scans = []
    for device in devices:
        scans.append(device.backup())
    results = await asyncio.gather(*scans)
    print(results)


async def main():
    parser = ArgumentParser()
    parser.add_argument("--scan", help="Scan a network to look for tasmota devices on.", required=False)
    parser.add_argument("--config", help="The config to look up tasmota devices.", required=False,
                        default="devices.json")
    parser.add_argument("--repl", help="Run a console", required=False, action='store_true')
    parser.add_argument("--backup", help="Backup devices", required=False, action='store_true')
    parser.add_argument("--restore", help="Restore devices", required=False, action='store_true')
    args = parser.parse_args()

    devices = load_devices(args.config)

    if args.scan:
        print(f'Scanning: {args.scan}')
        new_devices = await scan_devices(args.scan)
        for device in new_devices:
            if device is None:
                continue
            if device not in devices:
                devices.append(device)
        save_devices(args.config, devices)

    if args.backup:
        await backup(devices)
        save_devices(args.config, devices)

    if args.restore:
        await restore(devices)

    if args.repl:
        await repl(devices)


if __name__ == '__main__':
    asyncio.run(main())
