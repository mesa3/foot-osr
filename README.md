# Foot-OSR Control

A Python-based GUI application for synchronized control of dual OSR (OpenSourceRoadie) style haptic devices. This tool enables complex motion synchronization, WebSocket T-Code broadcasting, and fine-tuned control over multiple motion axes.

## Features

- **Dual Device Control**: Independently connect and manage two OSR devices via serial ports (supports high baud rates up to 921600).
- **Synchronized Motion**:
  - Adjustable speed (Hz), stroke length, and offset.
  - Variable phase shift (0-180°) for synchronous or alternating movement.
  - Multi-axis support: Stroke (L0), Pitch (R2), Roll (R1), and Twist (R0).
- **WebSocket Server**: Integrated T-Code WebSocket server for broadcasting motion data to external applications or remote clients.
- **Advanced Motion Modes**: Specialized modes like `v_stroke` with automated L2 (Lateral) compensation to maintain grip pressure during strokes.
- **Real-time Configuration**: Adjust pitch, roll, and twist amplitudes and offsets on the fly through an intuitive GUI.
- **Logging**: Built-in logging window to monitor connection status and device communication.

## Requirements

- **Python**: 3.7+ (Tested on 3.7.9)
- **Dependencies**:
  - `pyserial`: For serial communication with OSR devices.
  - `websockets`: For T-Code broadcasting.
  - `tkinter`: For the graphical user interface (usually included with Python).

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/mesa3/foot-osr.git
   cd foot-osr
   ```

2. Install the required packages:
   ```bash
   pip install pyserial websockets
   ```

3. Run the application:
   ```bash
   python dual_osr_control.py
   ```

### Using the Standalone Executable

If you don't have Python installed, you can use the pre-compiled version found in the `dist/` directory (Windows only):

1. Navigate to `dist/`.
2. Run `dual_osr_control.exe`.

## Usage

1. **Connect Devices**: Select the COM ports for Device A and Device B from the dropdown menus and click **Connect**.
2. **Configure Motion**:
   - Use the **Speed** slider to set frequency.
   - Adjust **Stroke** and **Phase Shift** for synchronization patterns.
   - Fine-tune **Pitch**, **Roll**, and **Twist** amplitudes.
3. **Start Motion**: Click the **Start** button to begin the synchronized motion loop.
4. **WebSocket**: The WebSocket server starts automatically on port `8766`. Clients can connect to receive real-time T-Code updates.

## Development

### Building the Executable

To build your own standalone `.exe` using PyInstaller:

```bash
pyinstaller --onefile --noconsole dual_osr_control.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
