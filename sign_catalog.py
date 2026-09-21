"""Display metadata only. Model class IDs/names remain authoritative."""
import re


def normalize(name):
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def sign_info(name):
    key = normalize(name)
    label = str(name).replace("_", " ").title().replace("Compulsary", "Compulsory")
    info = dict(label=label, icon="🚧", chip="SIGN", chip_class="info",
                meaning=f"Model prediction: {label}.",
                rule="Confirm the visible sign; this prediction may be incorrect.")
    speed = re.fullmatch(r"speed_?limit_?(\d+)", key)
    if speed:
        info.update(label=f"Speed limit {speed[1]} km/h", chip="REGULATORY",
                    meaning=f"A maximum-speed sign displaying {speed[1]} km/h.")
    descriptions = {
        "stop": ("Stop sign", "A stop sign.", "mandatory", "🛑"),
        "give_way": ("Give way", "A give-way sign.", "mandatory", "🚧"),
        "speedlimit": ("Speed limit", "A speed-limit sign; this model does not read its number.", "info", "🚧"),
        "trafficlight": ("Traffic light", "A physical traffic light; its active colour is not classified.", "info", "🚦"),
        "traffic_signal": ("Traffic signals ahead", "A warning sign for traffic signals ahead, not the current light state.", "warning", "🚦"),
        "crosswalk": ("Crosswalk (legacy class)", "The original dataset's crosswalk category; verify the marked object.", "warning", "🚸"),
        "pedestrian_crossing": ("Pedestrian crossing sign", "A pedestrian-crossing sign, not a detected pedestrian.", "warning", "🚸"),
        "school_ahead": ("School ahead", "A school-ahead warning sign.", "warning", "🚸"),
        "men_at_work": ("Roadworks", "A roadworks warning sign.", "warning", "🚧"),
        "hump_or_rough_road": ("Hump or rough road", "A hump or rough-road warning sign.", "warning", "🚧"),
        "no_entry": ("No entry", "A no-entry sign.", "mandatory", "⛔"),
        "no_parking": ("No parking", "A no-parking sign.", "info", "🚧"),
    }
    if key in descriptions:
        label, meaning, style, icon = descriptions[key]
        info.update(label=label, meaning=meaning, chip_class=style,
                    chip={"mandatory": "REGULATORY", "warning": "WARNING", "info": "SIGN"}[style], icon=icon)
    return info


def catalog(names):
    values = names.values() if isinstance(names, dict) else names
    return {name: sign_info(name) for name in values}
