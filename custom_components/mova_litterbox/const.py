"""Constants for the MOVA Litter Box (local) integration."""

DOMAIN = "mova_litterbox"

CONF_PORT = "port"

DEFAULT_PORT = 19974

# Fired with a did payload whenever a not-yet-seen device sends its first
# message, so sensor.py can create entities for it on the fly.
SIGNAL_NEW_DEVICE = f"{DOMAIN}_new_device"
# Fired with a did payload whenever that device's properties change.
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
