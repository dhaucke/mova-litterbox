"""Constants for the MOVA Litter Box (local) integration."""

DOMAIN = "mova_litterbox"

CONF_PORT = "port"
CONF_UPSTREAM = "upstream"

DEFAULT_PORT = 19974
# Public resolvers used to look up the real MOVA broker IP, bypassing
# whatever local DNS rewrite is redirecting the same hostname to us.
PUBLIC_DNS_SERVERS = ["1.1.1.1", "8.8.8.8"]

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
    # Confirmed 2026-09-04: captured a real app button tap as
    # set_properties siid=3/piid=13 value=1 (then value=0 shortly after),
    # followed by an event_occured(siid=4, eiid=9). Denis confirmed the
    # button he tapped was air purification/deodorizing, not the cleaning
    # cycle - so this is that toggle, not "start cleaning". Not yet
    # writable from HA (see broker.py - the proxy only relays/observes
    # so far, doesn't inject).
    "3.13": "Air Purification (observed, not yet controllable from HA)",
    # Confirmed 2026-09-04: Denis tapped "Desodorierungsflüssigkeit"
    # (deodorizing liquid) in the app, captured as set_properties
    # siid=3/piid=14 value=1, followed by event_occured(siid=4, eiid=10).
    "3.14": "Deodorizing Liquid (observed, not yet controllable from HA)",
}
