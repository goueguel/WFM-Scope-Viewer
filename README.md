# WFM Scope Viewer

WFM Scope Viewer is a desktop application for opening and inspecting Rigol
`.wfm` oscilloscope waveform files. It automatically detects the active analog
channels and presents the waveform display and file metadata side by side.

Each channel uses a consistent oscilloscope-style color across its trace,
legend, selector, and metadata card, making multi-channel captures easy to
interpret.

## Features

- Opens `.wfm` files using the file picker, `Ctrl+O`, or drag and drop
- Automatically detects one to four active analog channels
- Displays all channels overlaid on one plot or on separate plots
- Uses responsive 1×1, 1×2, and 2×2 layouts in separate-channel mode
- Provides oscilloscope-style colors, grid lines, and channel legends
- Supports panning, wheel zoom, box zoom, and automatic scaling
- Displays searchable file, trigger, timing, and channel metadata
- Formats values using compact engineering units, such as `335 mV/Div`,
  `100 µs/Div`, and `13 mV`
- Reports automatic parser selection as `Model Selection: Automatic`
- Limits displayed points when needed for responsive viewing of large captures
- Exports the current waveform display as a PNG image
- Reports the presence of logic channels in the metadata

> [!NOTE]
> This version focuses on visualizing analog oscilloscope channels. Logic-channel
> data may be reported in the metadata but is not plotted.

## Windows executable

The standalone Windows executable includes Python and the required packages, so
Python does not need to be installed on the destination computer.

To download an executable produced by GitHub Actions:

1. Open the repository's **Actions** tab.
2. Select a successful **Build Windows executable** run.
3. Download the **WFM-Scope-Viewer-Windows** artifact.
4. Extract the downloaded ZIP file completely.
5. Run `WFM_Scope_Viewer.exe`.

## Run from source

### Requirements

- Python 3.10 or newer
- Windows, macOS, or Linux

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py app.py
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

## Using the application

1. Launch WFM Scope Viewer.
2. Select **Open WFM**, press `Ctrl+O`, or drag a `.wfm` file into the window.
3. Choose **Overlay** to superimpose the active channels or **Separate** to
   display each channel on its own plot.
4. Use the mouse to pan or zoom and **Autoscale** to restore the full view.
5. Search the metadata panel when looking for a particular setting or value.
6. Select **Export PNG** to save the current waveform display.

## Project structure

```text
WFM-Scope-Viewer/
├── app.py
├── requirements.txt
├── README.md
├── test_app.py
└── .github/
    └── workflows/
        └── build-windows.yml
```

## File compatibility

WFM Scope Viewer uses the [`RigolWFM`](https://github.com/scottprahl/RigolWFM)
package to decode waveform files. Available metadata and file compatibility
depend on the oscilloscope family and the information stored in each file.
Unknown metadata fields are omitted rather than displayed incorrectly.

## Main dependencies

- [PySide6](https://doc.qt.io/qtforpython-6/) for the desktop interface
- [pyqtgraph](https://www.pyqtgraph.org/) for interactive waveform plotting
- [NumPy](https://numpy.org/) for waveform data handling
- [RigolWFM](https://github.com/scottprahl/RigolWFM) for `.wfm` parsing

## Troubleshooting

### The application takes time to open

This is normal for the standalone one-file executable because it extracts its
bundled components before starting.

### A waveform file does not open

Confirm that the file has a `.wfm` extension and was produced by a supported
Rigol oscilloscope. If the problem continues, run the source version from a
terminal to see the full error message.

### The plot becomes slow with a large capture

Reduce the display-point limit. This changes the number of points rendered on
screen but does not modify the source waveform file.
