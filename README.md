# WFM Scope Viewer

A desktop viewer for Rigol `.wfm` oscilloscope captures. It detects the active
analog channels in each file and keeps each channel's oscilloscope color
consistent between its trace, legend, selector, and metadata card.

## Features

- Open a `.wfm` file with the button, `Ctrl+O`, or drag and drop.
- Automatic support for one to four active analog channels.
- Switch between a single overlaid plot and separate channel plots.
- Separate view automatically uses 1×1, 1×2, 2×2, or 2×2-with-one-empty layouts.
- Pan, wheel zoom, box zoom, autoscale, and PNG export.
- Searchable file and per-channel metadata.
- Compact engineering units for scope settings (for example, `335 mV/Div`).
- Plain-language parser metadata (`Model Selection: Automatic`).
- Configurable display-point limit for responsive rendering of long captures.
- Logic-channel presence is reported in metadata (analog visualization is the
  focus of this version).

## Install and run

Python 3.10 or newer is recommended.

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py app.py
```

On macOS/Linux, activate with `source .venv/bin/activate` and use `python` in
place of `py`.

## Notes

The app uses the same `RigolWFM` parser as the supplied notebook code. File
metadata depends on what the parser exposes for the particular oscilloscope
family. Unknown fields are omitted rather than displayed incorrectly.
