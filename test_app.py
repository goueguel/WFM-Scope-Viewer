import numpy as np

from app import channel_settings, enabled_channels, human_number, model_selection_metadata


class Channel:
    def __init__(self, number, enabled=True):
        self.channel_number = number
        self.times = np.linspace(0, 1e-3, 100) if enabled else None
        self.volts = np.sin(np.linspace(0, 6.28, 100)) if enabled else None


class ChannelSettings:
    coupling = "DC"
    volt_per_division = 0.335
    volt_scale = 0.013
    probe_value = 10


class Capture:
    channels = [Channel(1), Channel(2, False), Channel(4)]


def test_enabled_channels_filters_and_sorts():
    assert [channel.number for channel in enabled_channels(Capture())] == [1, 4]


def test_human_number_prefixes():
    assert human_number(0.001, "s") == "1 ms"
    assert human_number(2_000_000, "Sa/s") == "2 MSa/s"


def test_channel_settings_use_engineering_units():
    rows = dict(channel_settings(ChannelSettings()))
    assert rows["Scale"] == "335 mV/Div"
    assert rows["Voltage scale"] == "13 mV"
    assert rows["Probe"] == "10×"


def test_auto_model_selection_has_plain_language_label():
    capture = type("Capture", (), {"user_name": "auto"})()
    assert model_selection_metadata(capture) == [("Model Selection", "Automatic")]
