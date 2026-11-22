"""Import every integration module against a fake `homeassistant` to catch
NameError/AttributeError that py_compile can see coming."""
import sys, types, importlib

def mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m

class _Any:
    def __getattr__(self, k): return k.lower()
class _Enum:
    def __getattr__(self, k): return k.lower()

any_obj = _Any()

class DataUpdateCoordinator:
    def __class_getitem__(cls, item): return cls
    def __init__(self, *a, **kw): pass
    async def async_shutdown(self): pass
class UpdateFailed(Exception): pass
class ConfigEntryAuthFailed(Exception): pass
class ConfigFlow:
    def __init_subclass__(cls, **kw): pass
class OptionsFlowWithConfigEntry:
    def __init__(self, config_entry): self.config_entry = config_entry
class CoordinatorEntity:
    def __class_getitem__(cls, item): return cls
    _attr_available = True
    def __init__(self, coordinator, context=None): self.coordinator = coordinator
    @property
    def available(self): return True

mod("homeassistant")
mod("homeassistant.config_entries", ConfigEntry=dict, ConfigFlow=ConfigFlow,
    ConfigFlowResult=object, OptionsFlowWithConfigEntry=OptionsFlowWithConfigEntry, Platform=any_obj)
mod("homeassistant.const", Platform=_Enum(), CONF_EMAIL="email", CONF_PASSWORD="password",
    PERCENTAGE="%", SIGNAL_STRENGTH_DECIBELS_MILLIWATT="dBm",
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER="ug/m3", CONCENTRATION_PARTS_PER_MILLION="ppm",
    UnitOfTemperature=_Enum())
mod("homeassistant.core", HomeAssistant=object, callback=lambda f: f)
mod("homeassistant.data_entry_flow", FlowResult=object)
mod("homeassistant.exceptions", ConfigEntryAuthFailed=ConfigEntryAuthFailed)
mod("homeassistant.helpers")
mod("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=DataUpdateCoordinator,
    UpdateFailed=UpdateFailed, CoordinatorEntity=CoordinatorEntity)
mod("homeassistant.helpers.entity", EntityCategory=_Enum())
mod("homeassistant.helpers.device_registry", CONNECTION_NETWORK_MAC="mac",
    DeviceInfo=dict, format_mac=lambda s: s)
mod("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
mod("homeassistant.components")
mod("homeassistant.components.sensor", SensorDeviceClass=_Enum(), SensorEntity=object,
    SensorStateClass=_Enum())

sys.path.insert(0, "custom_components")
pkg = importlib.import_module("aprilaire_iaq")
for name in ("const", "cognito", "parser", "api", "coordinator", "entity", "sensor", "config_flow"):
    m = importlib.import_module(f"aprilaire_iaq.{name}")
    print(f"  ok  {name}")
from aprilaire_iaq.const import DEFAULT_INTERVAL
print("DEFAULT_INTERVAL =", DEFAULT_INTERVAL)
