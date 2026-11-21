"""Standalone reader, no Home Assistant required.

    python3 cli.py <email> <password>
"""
import asyncio
import importlib
import pathlib
import sys
import types

import aiohttp

PKG = pathlib.Path(__file__).parent / "custom_components" / "aprilaire_iaq"
_pkg = types.ModuleType("aprilaire_iaq")          # load submodules without HA's imports
_pkg.__path__ = [str(PKG)]
sys.modules["aprilaire_iaq"] = _pkg
_api = importlib.import_module("aprilaire_iaq.api")


async def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    async with aiohttp.ClientSession(trust_env=False) as session:
        cloud = _api.AprilAireCloud(session, sys.argv[1], sys.argv[2])
        snap = await cloud.async_snapshot()
        print("account:", cloud.account_id)
        for did, dev in snap.items():
            print(f"\n{dev['name'] or 'Healthy Air Monitor'} [{did}] {dev['model']} fw={dev['firmware']}")
            print(f"  air quality: {dev['iaq_state']}   rssi: {dev['rssi']} dBm   as of {dev['as_of']}")
            for key, m in sorted(dev["measurements"].items()):
                print(f"  {m['label']:<14} {m.get('value')!s:<8} {m.get('unit') or '':<7} {m.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
