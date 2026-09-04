"""Constants for the MOVA Litter Box (local) integration."""

DOMAIN = "mova_litterbox"

CONF_DID = "did"
CONF_UID = "uid"
CONF_MODEL = "model"
CONF_MAC = "mac"
CONF_PORT = "port"

DEFAULT_PORT = 19974

SIGNAL_UPDATE = f"{DOMAIN}_update"

# siid.piid -> friendly name. Meaning is a best guess from observed traffic
# on 2026-09-04 (see mitm/state.json in the source repo for raw captures) -
# MOVA doesn't publish a MIoT spec for this model, so these are provisional
# until confirmed against real litter box behavior (cleaning cycle, bin
# full, etc).
KNOWN_PROPERTIES = {
    "1.5": "Serial Number",
    "5.1": "Mode",
    "2.1": "Status",
    "2.2": "Property 2.2",
    "2.3": "Property 2.3",
    "2.6": "Property 2.6",
    "2.10": "Property 2.10",
    "2.11": "Property 2.11",
    "3.13": "Consumable 1",
    "3.14": "Consumable 2",
}
