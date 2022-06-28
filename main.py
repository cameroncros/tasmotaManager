import base64
import io
import json
from cmd import Cmd
from concurrent.futures import ThreadPoolExecutor
from ipaddress import IPv4Network
from typing import Any, Tuple, List, Optional
from urllib.parse import urlencode

import requests


class Device:
    def __init__(self, address, data):
        self.address = str(address)
        self.data = data

    def __str__(self):
        return f'({self.address})'

    def __eq__(self, other):
        if not isinstance(other, Device):
            # don't attempt to compare against unrelated types
            return NotImplemented
        return self.address == other.address

    def __hash__(self):
        # necessary for instances to behave sanely in dicts and sets.
        return hash((self.address,))

    def send_command(self, command: str) -> Tuple["Device", Any]:
        args = {'cmnd': command}
        url = f'http://{self.address}:80/cm?{urlencode(args)}'
        try:
            resp = requests.get(url=url, timeout=5)
            json = resp.json()
            return self, json
        except Exception as e:
            return self, None

    def backup(self) -> bool:
        url = f'http://{self.address}:80/dl'
        try:
            resp = requests.get(url=url)
            config = resp.raw()
            self.data = {'config': base64.b64encode(config).decode('utf-8')}
            return True
        except Exception as e:
            return False

    def restore(self) -> bool:
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


class CommandParser(Cmd):
    prompt = 'tasmotaManager> '

    def __init__(self):
        super().__init__()
        self.devices: List[Device] = []
        self.do_load()

    @staticmethod
    def scan_address(address) -> Optional[Device]:
        device = Device(address, {})
        _, response = device.send_command('Status 2')
        if response is not None and 'tasmota' in response['StatusFWR']['Version']:
            print(f'Found device: {address}')
            return device
        return None

    def do_scan(self, address_range: str):
        """
        Scan an address range for devices.
        :param address_range: The address range to scan
        """
        net_address = IPv4Network(address_range)
        with ThreadPoolExecutor(max_workers=1024) as executor:
            scans = []
            for address in net_address:
                scans.append(executor.submit(self.scan_address, address))
            results = [scan.result() for scan in scans]
        for result in results:
            if result is not None and result not in self.devices:
                self.devices.append(result)

    def do_cmd(self, line):
        """
        Execute a command on all devices
        :arg line: Command to send
        """
        with ThreadPoolExecutor(max_workers=len(self.devices) + 1) as executor:
            threads = []
            for device in self.devices:
                threads.append(executor.submit(device.send_command, line))
            results = [thread.result() for thread in threads]
            for result in results:
                print(f"{result[0]}: {result[1]}")
            print(f"\n")

    def default(self, line):
        self.do_cmd(line)

    def do_save(self, file="devices.json"):
        """
        Save devices to file
        :param file: Default file is devices.json
        """
        config = {}
        for device in self.devices:
            config[str(device.address)] = device.get_config()
        with open(file, 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

    def do_load(self, file="devices.json"):
        """
        Load devices from file
        :param file: The file to load device config from
        """
        try:
            with open(file, 'r') as f:
                config = json.load(f)
                for address in config:
                    self.devices.append(Device(address, data=config[address]))
        except:
            pass

    def do_print(self, _):
        """
        Print all devices
        """
        for device in self.devices:
            print(device)

    def do_backup(self, _):
        """
        Backup all devices
        """
        with ThreadPoolExecutor(max_workers=len(self.devices) + 1) as executor:
            threads = []
            for device in self.devices:
                threads.append(executor.submit(device.backup))
            results = [thread.results() for thread in threads]
            print(results)

    def do_restore(self, _):
        """
        Restore all devices
        """
        with ThreadPoolExecutor(max_workers=len(self.devices) + 1) as executor:
            threads = []
            for device in self.devices:
                threads.append(executor.submit(device.restore))
            results = [thread.results() for thread in threads]
            print(results)

    def do_quit(self, _):
        """
        Quit!
        """
        return True


def main():
    parser = CommandParser()
    parser.cmdloop()


if __name__ == '__main__':
    main()
