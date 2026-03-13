import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import math
import logging

import asyncio
import websockets

class TCodeWSServer:
    def __init__(self, port=8766):
        self.port = port
        self.clients = set()
        self.loop = None
        self.running = False
        self.thread = None
        self.server = None

    async def _handler(self, websocket, path=None):
        self.clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self.clients.remove(websocket)

    def _start_server(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def _serve():
            try:
                self.server = await websockets.serve(self._handler, "0.0.0.0", self.port)
                logger.info(f"WebSocket server started on port {self.port}")
            except OSError as e:
                logger.error(f"Failed to start WebSocket server on port {self.port}: {e}")
                self.running = False
                return

        self.loop.run_until_complete(_serve())
        if self.running:
            self.loop.run_forever()

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._start_server, daemon=True)
            self.thread.start()

    def stop(self):
        if self.running and self.loop:
            self.running = False
            # Safely stop server without hanging
            try:
                if self.server:
                    self.loop.call_soon_threadsafe(self.server.close)
                self.loop.call_soon_threadsafe(self.loop.stop)
            except RuntimeError:
                pass # Event loop might be already closed
            logger.info(f"WebSocket server {self.port} stopped")

    def broadcast(self, message):
        if not self.running or not self.clients or not self.loop:
            return

        async def _broadcast():
            if self.clients:
                await asyncio.gather(*[client.send(message) for client in self.clients], return_exceptions=True)

        asyncio.run_coroutine_threadsafe(_broadcast(), self.loop)


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class DualOSRController:
    def __init__(self):
        self.ws_server_a = None
        self.ws_server_b = None
        self.ser_a = None
        self.ser_b = None
        self.running = False
        self.thread = None

        # Motion parameters
        self.speed = 1.0       # Hz
        self.stroke = 50.0     # % (0-100)
        self.offset = 50.0     # % (0-100)
        self.phase_shift = 180 # Degrees (0 = sync, 180 = alternating)

        # New Motion Parameters
        self.pitch_amp = 50.0  # R2
        self.roll_amp = 50.0   # R1
        self.twist_amp = 50.0  # R0
        self.base_squeeze = 50.0 # Base L0 offset
        self.ankle_angle_offset = 50.0 # Base R2 offset
        self.roll_angle_offset = 50.0 # Base R1 offset
        self.motion_mode = "v_stroke"
        self.reverse_l2 = False
        self.tilt_compensation = 0.0 # L2 base tilt offset
        # Device status
        self.connected_a = False
        self.connected_b = False
        self.current_phase = 0.0

        # Height Offset Parameters (L0 offset)
        self.height_offset_a = 0  # T-Code raw value offset (-9999 to 9999)
        self.height_offset_b = 0
        self.is_initializing = False


    def _connect_device(self, device_id, port, baudrate):
        ser_attr = f"ser_{device_id}"
        conn_attr = f"connected_{device_id}"
        label = f"Device {device_id.upper()}"

        ser = getattr(self, ser_attr)
        if ser and ser.is_open:
            ser.close()

        try:
            new_ser = serial.Serial(port, baudrate, timeout=0.1)
            setattr(self, ser_attr, new_ser)
            setattr(self, conn_attr, True)
            logger.info(f"Connected {label} on {port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect {label}: {e}")
            setattr(self, conn_attr, False)
            return False

    def connect_device_a(self, port, baudrate=115200):
        return self._connect_device('a', port, baudrate)

    def connect_device_b(self, port, baudrate=115200):
        return self._connect_device('b', port, baudrate)

    def disconnect_all(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.2)

        if self.ser_a and self.ser_a.is_open:
            self.ser_a.close()
        if self.ser_b and self.ser_b.is_open:
            self.ser_b.close()
        self.connected_a = False
        self.connected_b = False
        logger.info("All devices disconnected")

    def go_to_neutral(self):
        self.is_initializing = True

        # Calculate neutral positions applying the offsets
        l0_a = max(0, min(9999, 5000 + getattr(self, "height_offset_a", 0)))
        l0_b = max(0, min(9999, 5000 + getattr(self, "height_offset_b", 0)))

        cmd_a = f"L0{l0_a:04d} I1000"
        cmd_b = f"L0{l0_b:04d} I1000"

        self._send_cmd(self.ser_a, cmd_a, self.ws_server_a)
        self._send_cmd(self.ser_b, cmd_b, self.ws_server_b)
        logger.info(f"Initialized to Neutral - A: {l0_a}, B: {l0_b}")

    def start_motion(self):
        if not self.running:
            self.is_initializing = False  # Clear init flag on actual motion start
            self.running = True
            self.thread = threading.Thread(target=self.motion_loop, daemon=True)
            self.thread.start()
            logger.info("Motion started")

    def stop_motion(self):
        self.running = False
        # Do not block the GUI thread waiting for serial writes or sleep to finish
        # if self.thread and self.thread.is_alive():
        #     self.thread.join(timeout=0.1)
        logger.info("Motion stopped signal sent (waiting for thread to finish in background)")

    def _send_cmd(self, ser, cmd, ws_server=None):
        if ws_server:
            ws_server.broadcast(f"{cmd}\n")
        if ser and ser.is_open:
            try:
                ser.write(f"{cmd}\r\n".encode())
            except Exception as e:
                logger.error(f"Serial write error: {e}")
                # We don't close here to avoid thread safety issues with GUI,
                # but the error is now visible in the log.

    def calculate_frame(self):
            phase_a = self.current_phase
            phase_b = phase_a + math.radians(self.phase_shift)

            # Amplitudes (0-5000)
            amp_l0 = (self.stroke / 100.0) * 5000
            amp_l2 = amp_l0  # 45 deg geometry means L1 compensation is 1:1 with L0
            amp_r2 = (self.pitch_amp / 100.0) * 5000
            amp_r1 = (self.roll_amp / 100.0) * 5000
            amp_r0 = (self.twist_amp / 100.0) * 5000

            # Centers (0-9999)
            center_l0 = (self.base_squeeze / 100.0) * 9999
            center_l2 = 5000 + (self.tilt_compensation / 100.0) * 5000
            center_a_r1 = (self.roll_angle_offset / 100.0) * 9999
            center_b_r1 = 9999 - center_a_r1 # Mirror R1 for Device B so they tilt in the same physical direction
            center_r0 = 5000 # Neutral twist
            center_rx = center_a_r1 # Backwards compatibility for unmodified modes
            center_r2 = (self.ankle_angle_offset / 100.0) * 9999

            # Clamp L0
            if center_l0 - amp_l0 < 0: center_l0 = amp_l0
            if center_l0 + amp_l0 > 9999: center_l0 = 9999 - amp_l0

            # L2 Compensation direction multiplier (based on wall mount orientation)
            l2_mult = -1.0 if self.reverse_l2 else 1.0

            def clamp(val):
                return max(0, min(9999, int(val)))

            # Apply height offset
            center_a_l0 = center_l0 + self.height_offset_a
            center_b_l0 = center_l0 + self.height_offset_b

            cmd_a_parts = []
            cmd_b_parts = []

            if self.motion_mode == "v_stroke":
                # Pure parallel sliding stroke
                z_motion = amp_l0 * math.sin(phase_a)
                pos_l0 = center_l0 + z_motion

                # Compensate laterally (L2) to maintain grip pressure while stroking
                pos_a_l2 = center_l2 - (z_motion * l2_mult)
                pos_b_l2 = center_l2 + (z_motion * l2_mult)

                cmd_a_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(center_r2):04d}", f"R1{clamp(center_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(center_r2):04d}", f"R1{clamp(center_b_r1):04d}"])


            elif self.motion_mode == "wave_rub_up_down":
                # Up-down wave rubbing (上下波浪形揉搓)
                # Alternating vertical strokes with R1 rolling the arch up and down the shaft
                z_motion_a = amp_l0 * math.sin(phase_a)
                z_motion_b = amp_l0 * math.sin(phase_b) # phase_b is 180 deg out because it's no longer in sync list

                pos_a_l0 = center_l0 + z_motion_a
                pos_b_l0 = center_l0 + z_motion_b

                pos_a_l2 = center_l2 - (z_motion_a * l2_mult)
                pos_b_l2 = center_l2 + (z_motion_b * l2_mult)

                # R1 rolls dynamically out of phase with the stroke to create a massaging wave
                # Using standard mirror for B + phase_b naturally achieves the physical alternating roll
                pos_a_r1 = center_a_r1 + amp_r1 * math.cos(phase_a)
                pos_b_r1 = center_b_r1 - amp_r1 * math.cos(phase_b)

                cmd_a_parts.extend([f"L0{clamp(pos_a_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(center_r2):04d}", f"R1{clamp(pos_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_b_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(center_r2):04d}", f"R1{clamp(pos_b_r1):04d}"])

            elif self.motion_mode == "wave_rub_front_back":
                # Front-back wave rubbing (前后波浪形揉搓)
                # Parallel sliding stroke with R2 (Pitch) pitching the toe/heel against the shaft
                z_motion = amp_l0 * math.sin(phase_a)
                pos_l0 = center_l0 + z_motion

                pos_a_l2 = center_l2 - (z_motion * l2_mult)
                pos_b_l2 = center_l2 + (z_motion * l2_mult)

                # R2 pitches dynamically to wipe front/back at a higher frequency (2x)
                fast_phase = phase_a * 2.0
                pos_a_r2 = center_r2 + amp_r2 * math.cos(fast_phase)
                pos_b_r2 = center_r2 - amp_r2 * math.cos(fast_phase) # Alternating rapid pitch

                cmd_a_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(pos_a_r2):04d}", f"R1{clamp(center_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(pos_b_r2):04d}", f"R1{clamp(center_b_r1):04d}"])

            elif self.motion_mode == "static_rub_front_back":
                # Static front-back rubbing (原地前后波浪形揉搓)
                # No vertical movement. R2 (Pitch) pitches the toe/heel against the shaft.
                pos_l0 = center_l0
                pos_a_l2 = center_l2
                pos_b_l2 = center_l2

                # R2 pitches dynamically to wipe front/back at a higher frequency (2x)
                fast_phase = phase_a * 2.0
                pos_a_r2 = center_r2 + amp_r2 * math.cos(fast_phase)
                pos_b_r2 = center_r2 - amp_r2 * math.cos(fast_phase) # Alternating rapid pitch

                cmd_a_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(pos_a_r2):04d}", f"R1{clamp(center_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(pos_b_r2):04d}", f"R1{clamp(center_b_r1):04d}"])
            elif self.motion_mode == "alternating_step":
                # Alternating strokes with parallel L2 compensation
                z_motion_a = amp_l0 * math.sin(phase_a)
                z_motion_b = amp_l0 * math.sin(phase_b)

                pos_a_l0 = center_l0 + z_motion_a
                pos_b_l0 = center_l0 + z_motion_b

                pos_a_l2 = center_l2 - (z_motion_a * l2_mult)
                pos_b_l2 = center_l2 + (z_motion_b * l2_mult)

                # Dynamic Alternating Kneading
                pos_a_r2 = center_r2 + amp_r2 * math.cos(phase_a)
                pos_b_r2 = center_r2 - amp_r2 * math.cos(phase_b)

                pos_a_r1 = center_a_r1 + amp_r1 * math.sin(phase_a)
                pos_b_r1 = center_b_r1 - amp_r1 * math.sin(phase_b)

                cmd_a_parts.extend([f"L0{clamp(pos_a_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(pos_a_r2):04d}", f"R1{clamp(pos_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_b_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(pos_b_r2):04d}", f"R1{clamp(pos_b_r1):04d}"])

            elif self.motion_mode == "wrapping_twist":
                # Hold a constant close squeeze (L0).
                # Roll soles inwards (R1). Symmetrically relative to the center.
                pos_a_r1 = center_a_r1 + amp_r1 * math.sin(phase_a)
                pos_b_r1 = center_b_r1 - amp_r1 * math.sin(phase_a) # Mirror roll inwards

                # Alternate twisting to rub the sides (R0)
                pos_a_r0 = center_r0 + amp_r0 * math.cos(phase_a)
                pos_b_r0 = center_r0 + amp_r0 * math.cos(phase_b) # Alternating twist

                cmd_a_parts.extend([f"L0{clamp(center_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"R1{clamp(pos_a_r1):04d}", f"R0{clamp(pos_a_r0):04d}"])
                cmd_b_parts.extend([f"L0{clamp(center_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"R1{clamp(pos_b_r1):04d}", f"R0{clamp(pos_b_r0):04d}"])

            elif self.motion_mode == "sole_rub":
                pos_a_r2 = center_r2 + amp_r2 * math.sin(phase_a)
                pos_b_r2 = center_r2 + amp_r2 * math.sin(phase_b)

                pos_a_r1 = center_a_r1 + amp_r1 * math.cos(phase_a)
                pos_b_r1 = center_b_r1 + amp_r1 * math.cos(phase_b)

                cmd_a_parts.extend([f"L0{clamp(center_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(center_l2):04d}", f"R2{clamp(pos_a_r2):04d}", f"R1{clamp(pos_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(center_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(center_l2):04d}", f"R2{clamp(pos_b_r2):04d}", f"R1{clamp(pos_b_r1):04d}"])

            elif self.motion_mode == "toe_tease":
                # Quick flickering pitch (R2) to tap the toes.
                # L0 remains relatively steady but close.
                # Use a 2x frequency multiplier for a faster "teasing" feel.
                fast_phase_a = phase_a * 2.0
                fast_phase_b = phase_b * 2.0

                # Toes point "down" to tap towards the center
                # Sweep between 5000 and (5000 - amp_r2)
                pos_a_r2 = center_r2 - (amp_r2 / 2.0) - (amp_r2 / 2.0) * math.sin(fast_phase_a)
                pos_b_r2 = center_r2 - (amp_r2 / 2.0) - (amp_r2 / 2.0) * math.sin(fast_phase_b)

                # Slight pulsing L0
                pos_l0 = center_l0 + (amp_l0 * 0.1) * math.sin(phase_a)

                cmd_a_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"R2{clamp(pos_a_r2):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"R2{clamp(pos_b_r2):04d}"])

            elif self.motion_mode == "edge_stroking":
                # Feet roll heavily INWARDS (R1) to create a tight V-groove with the soles touching.
                pos_a_r1 = center_a_r1 + amp_r1
                pos_b_r1 = center_b_r1 - amp_r1

                # L0 synchronously strokes up and down the groove
                z_motion = amp_l0 * math.sin(phase_a)
                pos_l0 = center_l0 + z_motion

                # Compensate laterally
                pos_a_l2 = center_l2 - (z_motion * l2_mult)
                pos_b_l2 = center_l2 + (z_motion * l2_mult)

                # Fix pitch to stay parallel instead of bobbing up and down
                pos_r2 = center_r2

                cmd_a_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R1{clamp(pos_a_r1):04d}", f"R2{clamp(pos_r2):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R1{clamp(pos_b_r1):04d}", f"R2{clamp(pos_r2):04d}"])

            elif self.motion_mode == "heel_press":
                # Toes pitched heavily UP (away from target) to expose the heels.
                pos_r2 = center_r2 + amp_r2

                # Deep, slow squeezing L0
                slow_phase = phase_a * 0.5
                pos_l0 = center_l0 + amp_l0 * math.sin(slow_phase)

                # Twisting (R0) slightly back and forth to grind the heels
                pos_a_r0 = center_r0 + amp_r0 * math.cos(slow_phase)
                pos_b_r0 = center_r0 - amp_r0 * math.cos(slow_phase)

                cmd_a_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"R2{clamp(pos_r2):04d}", f"R0{clamp(pos_a_r0):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"R2{clamp(pos_r2):04d}", f"R0{clamp(pos_b_r0):04d}"])

            elif self.motion_mode == "circling_tease":
                pos_a_r1 = center_a_r1 + amp_r1 * math.sin(phase_a)
                pos_b_r1 = center_b_r1 - amp_r1 * math.sin(phase_a)

                pos_a_r2 = center_r2 + amp_r2 * math.cos(phase_a)
                pos_b_r2 = center_r2 + amp_r2 * math.cos(phase_a)

                cmd_a_parts.extend([f"L0{clamp(center_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(center_l2):04d}", f"R1{clamp(pos_a_r1):04d}", f"R2{clamp(pos_a_r2):04d}"])
                cmd_b_parts.extend([f"L0{clamp(center_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(center_l2):04d}", f"R1{clamp(pos_b_r1):04d}", f"R2{clamp(pos_b_r2):04d}"])


            elif self.motion_mode == "asymmetric_sprint":
                # Asymmetric Sprint (双机非对称冲刺)
                # One foot strokes rapidly while the other holds still, then they switch.

                # Slow phase controls the turn (e.g., switch every 2.5 full cycles)
                turn_phase = phase_a * 0.2
                # Fast phase for the sprint
                sprint_phase = phase_a * 2.5

                if math.sin(turn_phase) > 0:
                    # Device A's turn to sprint
                    z_motion_a = amp_l0 * math.sin(sprint_phase)
                    z_motion_b = 0 # B holds still
                else:
                    # Device B's turn to sprint
                    z_motion_a = 0 # A holds still
                    z_motion_b = amp_l0 * math.sin(sprint_phase)

                pos_a_l0 = center_l0 + z_motion_a
                pos_a_l2 = center_l2 - (z_motion_a * l2_mult)

                pos_b_l0 = center_l0 + z_motion_b
                pos_b_l2 = center_l2 + (z_motion_b * l2_mult)

                # Add a little teasing pitch wag to the active foot
                pos_a_r2 = center_r2 + (amp_r2 * 0.5 * math.cos(sprint_phase) if z_motion_a != 0 else 0)
                pos_b_r2 = center_r2 - (amp_r2 * 0.5 * math.cos(sprint_phase) if z_motion_b != 0 else 0)

                cmd_a_parts.extend([f"L0{clamp(pos_a_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(pos_a_r2):04d}", f"R1{clamp(center_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_b_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(pos_b_r2):04d}", f"R1{clamp(center_b_r1):04d}"])

            elif self.motion_mode == "foot_slap":
                # Foot Slap V3 (严谨节奏的单脚轮流大力扇耳光)
                # 节奏: A蓄力 -> A扇! -> A退回 -> B蓄力 -> B扇! -> B退回

                # director 进度 0.0 到 1.0 (控制完整的左右脚一轮)
                director = ( (phase_a * 0.4) % (2 * math.pi) ) / (2 * math.pi)

                # 定义几个关键位置
                park_l0 = center_l0 - amp_l0 * 0.5   # 停靠时稍微后退
                park_l2_offset = amp_l0 * 0.8        # 停靠时向外侧躲开

                windup_l0 = center_l0 - amp_l0       # 蓄力时退到最远
                windup_l2_offset = amp_l0            # 蓄力时张到最大
                windup_r2 = center_r2 + amp_r2       # 蓄力时脚腕上翻

                slap_l0 = center_l0 + amp_l0 * 0.5   # 扇下去时往前怼
                slap_l2_offset = 0                   # 扇下去时直击中心
                slap_r2 = center_r2 - amp_r2         # 扇下去时脚腕下压（鞭打）

                # 辅助函数：在两点之间线性插值
                def lerp(start, end, progress):
                    return start + (end - start) * progress

                def get_kinematics(local_prog):
                    # 0.0-0.6: 缓慢蓄力 (Windup)
                    # 0.6-0.7: 瞬间爆击 (Slap!)
                    # 0.7-1.0: 快速收回 (Recover to Park)
                    if local_prog < 0.6:
                        p = local_prog / 0.6
                        l0 = lerp(park_l0, windup_l0, p)
                        l2_off = lerp(park_l2_offset, windup_l2_offset, p)
                        r2 = lerp(center_r2, windup_r2, p)
                    elif local_prog < 0.7:
                        p = (local_prog - 0.6) / 0.1
                        l0 = lerp(windup_l0, slap_l0, p)
                        l2_off = lerp(windup_l2_offset, slap_l2_offset, p)
                        r2 = lerp(windup_r2, slap_r2, p)
                    else:
                        p = (local_prog - 0.7) / 0.3
                        l0 = lerp(slap_l0, park_l0, p)
                        l2_off = lerp(slap_l2_offset, park_l2_offset, p)
                        r2 = lerp(slap_r2, center_r2, p)
                    return l0, l2_off, r2

                if director < 0.5:
                    # Device A's turn
                    local_a = director / 0.5
                    l0_a, l2_off_a, r2_a = get_kinematics(local_a)

                    pos_a_l0 = l0_a
                    pos_a_l2 = center_l2 - (l2_off_a * l2_mult)
                    pos_a_r2 = r2_a
                    pos_a_r1 = center_a_r1

                    # B is parked
                    pos_b_l0 = park_l0
                    pos_b_l2 = center_l2 + (park_l2_offset * l2_mult)
                    pos_b_r2 = center_r2
                    pos_b_r1 = center_b_r1
                else:
                    # Device B's turn
                    local_b = (director - 0.5) / 0.5
                    l0_b, l2_off_b, r2_b = get_kinematics(local_b)

                    # A is parked
                    pos_a_l0 = park_l0
                    pos_a_l2 = center_l2 - (park_l2_offset * l2_mult)
                    pos_a_r2 = center_r2
                    pos_a_r1 = center_a_r1

                    pos_b_l0 = l0_b
                    pos_b_l2 = center_l2 + (l2_off_b * l2_mult)
                    pos_b_r2 = r2_b
                    pos_b_r1 = center_b_r1

                cmd_a_parts.extend([f"L0{clamp(pos_a_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(pos_a_r2):04d}", f"R1{clamp(pos_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_b_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(pos_b_r2):04d}", f"R1{clamp(pos_b_r1):04d}"])

            elif self.motion_mode == "glans_torture":
                # Glans Torture (龟头折磨)
                # Devices stay at the far extension limit and vibrate/knead intensely.
                tip_center_l0 = center_l0 + (amp_l0 * 0.8)

                # High frequency, micro amplitude
                micro_amp_l0 = amp_l0 * 0.15
                fast_phase = phase_a * 4.0 # 4x speed vibration

                # Micro vertical vibration
                z_motion = micro_amp_l0 * math.sin(fast_phase)

                pos_l0 = tip_center_l0 + z_motion

                # L2 compensates the new tip center + micro vibration
                base_l2_offset = amp_l0 * 0.8 * l2_mult
                micro_l2_offset = z_motion * l2_mult

                pos_a_l2 = center_l2 - base_l2_offset - micro_l2_offset
                pos_b_l2 = center_l2 + base_l2_offset + micro_l2_offset

                # Intense, fast kneading
                pos_a_r1 = center_a_r1 + (amp_r1 * 0.5) * math.sin(fast_phase * 1.5)
                pos_b_r1 = center_b_r1 - (amp_r1 * 0.5) * math.sin(fast_phase * 1.5)

                pos_a_r2 = center_r2 + (amp_r2 * 0.5) * math.cos(fast_phase)
                pos_b_r2 = center_r2 - (amp_r2 * 0.5) * math.cos(fast_phase)

                cmd_a_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(pos_a_r2):04d}", f"R1{clamp(pos_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(pos_b_r2):04d}", f"R1{clamp(pos_b_r1):04d}"])

            elif self.motion_mode == "edging_sole_show":
                # Edging Sole Show (寸止展示脚底)
                # Fast strokes followed by a sudden stop, spreading wide, and pitching up.

                # Director phase: slow cycle to toggle between stroking and showing
                director = math.sin(phase_a * 0.2)
                fast_phase = phase_a * 2.0

                if director > 0:
                    # Stroking Phase (Fast parallel v_stroke)
                    z_motion = amp_l0 * math.sin(fast_phase)

                    pos_l0 = center_l0 + z_motion
                    pos_a_l2 = center_l2 - (z_motion * l2_mult)
                    pos_b_l2 = center_l2 + (z_motion * l2_mult)

                    # Normal pitch and roll
                    pos_a_r2 = center_r2
                    pos_b_r2 = center_r2
                    pos_a_r1 = center_a_r1
                    pos_b_r1 = center_b_r1

                else:
                    # Show Phase
                    pos_l0 = center_l0 - amp_l0
                    pos_a_l2 = center_l2 - (amp_l0 * l2_mult)
                    pos_b_l2 = center_l2 + (amp_l0 * l2_mult)

                    # Pitch (R2) heavily up
                    pos_a_r2 = center_r2 + amp_r2
                    pos_b_r2 = center_r2 + amp_r2

                    pos_a_r1 = center_a_r1
                    pos_b_r1 = center_b_r1

                cmd_a_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(pos_a_r2):04d}", f"R1{clamp(pos_a_r1):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(pos_b_r2):04d}", f"R1{clamp(pos_a_r1):04d}"])
            elif self.motion_mode == "single_foot_tease_left":
                fast_phase_a = phase_a * 2.0
                pos_a_r2 = center_r2 - (amp_r2 / 2.0) - (amp_r2 / 2.0) * math.sin(fast_phase_a)

                z_motion_a = (amp_l0 * 0.1) * math.sin(phase_a)
                pos_a_l0 = center_l0 + z_motion_a
                pos_a_l2 = center_l2 - (z_motion_a * l2_mult)

                pos_b_r2 = center_r2
                pos_b_l0 = center_l0
                pos_b_l2 = center_l2

                cmd_a_parts.extend([f"L0{clamp(pos_a_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(pos_a_r2):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_b_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(pos_b_r2):04d}"])

            elif self.motion_mode == "single_foot_tease_right":
                fast_phase_b = phase_a * 2.0
                pos_a_r2 = center_r2
                pos_a_l0 = center_l0

                pos_b_r2 = center_r2 - (amp_r2 / 2.0) - (amp_r2 / 2.0) * math.sin(fast_phase_b)
                pos_b_l0 = center_l0 + (amp_l0 * 0.1) * math.sin(phase_a)

                cmd_a_parts.extend([f"L0{clamp(pos_a_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"R2{clamp(pos_a_r2):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_b_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"R2{clamp(pos_b_r2):04d}"])

            elif self.motion_mode == "single_foot_stroke_left":
                z_motion_a = amp_l0 * math.sin(phase_a)
                pos_a_l0 = center_l0 + z_motion_a
                pos_a_l2 = center_l2 - (z_motion_a * l2_mult)
                pos_b_l0 = center_l0
                pos_b_l2 = center_l2

                cmd_a_parts.extend([f"L0{clamp(pos_a_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(center_r2):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_b_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(center_r2):04d}"])

            elif self.motion_mode == "single_foot_stroke_right":
                pos_a_l0 = center_l0
                pos_a_l2 = center_l2
                z_motion_b = amp_l0 * math.sin(phase_a)
                pos_b_l0 = center_l0 + z_motion_b
                pos_b_l2 = center_l2 + (z_motion_b * l2_mult)

                cmd_a_parts.extend([f"L0{clamp(pos_a_l0 + getattr(self, 'height_offset_a', 0)):04d}", f"L2{clamp(pos_a_l2):04d}", f"R2{clamp(center_r2):04d}"])
                cmd_b_parts.extend([f"L0{clamp(pos_b_l0 + getattr(self, 'height_offset_b', 0)):04d}", f"L2{clamp(pos_b_l2):04d}", f"R2{clamp(center_r2):04d}"])

            else: # fallback
                pos_a = center_l0 + amp_l0 * math.sin(phase_a)
                pos_b = center_l0 + amp_l0 * math.sin(phase_b)
                cmd_a_parts.append(f"L0{clamp(pos_a + getattr(self, 'height_offset_a', 0)):04d}")
                cmd_b_parts.append(f"L0{clamp(pos_b + getattr(self, 'height_offset_b', 0)):04d}")

            return " ".join(cmd_a_parts), " ".join(cmd_b_parts)

    def motion_loop(self):
        self.current_phase = 0.0
        dt = 0.02 # 50Hz update rate

        while self.running:
            start_time = time.time()

            cmd_a_base, cmd_b_base = self.calculate_frame()

            cmd_a = cmd_a_base + " I20"
            cmd_b = cmd_b_base + " I20"

            self._send_cmd(self.ser_a, cmd_a, self.ws_server_a)
            self._send_cmd(self.ser_b, cmd_b, self.ws_server_b)

            # Update phase instead of absolute time to allow smooth frequency changes
            self.current_phase += 2 * math.pi * self.speed * dt
            # Keep phase in [0, 2pi] to avoid float precision issues over time
            self.current_phase %= 2 * math.pi

            elapsed = time.time() - start_time
            sleep_time = max(0, dt - elapsed)
            time.sleep(sleep_time)        # Center devices on stop with offset
        l0_a = max(0, min(9999, 5000 + self.height_offset_a))
        l0_b = max(0, min(9999, 5000 + self.height_offset_b))
        self._send_cmd(self.ser_a, f"L0{l0_a:04d} I1000", self.ws_server_a)
        self._send_cmd(self.ser_b, f"L0{l0_b:04d} I1000", self.ws_server_b)
        logger.info("Motion stopped and devices centered (with offset)")

class DualOSRGui:
    def __init__(self, root):
        self.root = root
        self.root.title("Dual OSR Footjob Simulator")
        self.root.geometry("600x900")
        self.controller = DualOSRController()

        # Create a main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=1)

        # Create a canvas
        self.canvas = tk.Canvas(self.main_frame)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        # Add a scrollbar to the canvas
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind(
            '<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Create another frame inside the canvas
        self.scrollable_frame = ttk.Frame(self.canvas)

        # Add that new frame to a window in the canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # Configure width of scrollable frame to match canvas
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        # Bind mousewheel
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)

        self.create_widgets()

    def _on_canvas_configure(self, event):
        # update inner frame width to fill the canvas
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        # Windows/Mac/Linux cross platform
        if hasattr(event, 'num') and event.num == 5 or getattr(event, 'delta', 0) < 0:
            self.canvas.yview_scroll(1, "units")
        elif hasattr(event, 'num') and event.num == 4 or getattr(event, 'delta', 0) > 0:
            self.canvas.yview_scroll(-1, "units")

    def create_widgets(self):
        # Change parent frame variable for widgets
        parent = self.scrollable_frame
        # --- WebSocket Section ---
        ws_frame = ttk.LabelFrame(self.scrollable_frame, text="WebSocket Servers")
        ws_frame.pack(fill="x", padx=10, pady=5)

        row_ws = ttk.Frame(ws_frame)
        row_ws.pack(fill="x", padx=5, pady=2)

        self.enable_ws = tk.BooleanVar(value=True)
        ttk.Checkbutton(row_ws, text="Enable WS Servers", variable=self.enable_ws).pack(side="left", padx=5)

        ttk.Label(row_ws, text="Port A:").pack(side="left", padx=(10, 2))
        self.ws_port_a = tk.IntVar(value=8766)
        ttk.Entry(row_ws, textvariable=self.ws_port_a, width=6).pack(side="left")

        ttk.Label(row_ws, text="Port B:").pack(side="left", padx=(10, 2))
        self.ws_port_b = tk.IntVar(value=8767)
        ttk.Entry(row_ws, textvariable=self.ws_port_b, width=6).pack(side="left")

        # --- Connection Section ---
        conn_frame = ttk.LabelFrame(self.scrollable_frame, text="Connections")
        conn_frame.pack(fill="x", padx=10, pady=5)

        # Device A
        dev_a_frame = ttk.Frame(conn_frame)
        dev_a_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(dev_a_frame, text="Device A (Left):").pack(side="left")
        self.port_a = tk.StringVar()
        self.combo_a = ttk.Combobox(dev_a_frame, textvariable=self.port_a, width=15)
        self.combo_a.pack(side="left", padx=5)
        self.btn_connect_a = ttk.Button(dev_a_frame, text="Connect", command=self.toggle_connect_a)
        self.btn_connect_a.pack(side="left")

        # Device B
        dev_b_frame = ttk.Frame(conn_frame)
        dev_b_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(dev_b_frame, text="Device B (Right):").pack(side="left")
        self.port_b = tk.StringVar()
        self.combo_b = ttk.Combobox(dev_b_frame, textvariable=self.port_b, width=15)
        self.combo_b.pack(side="left", padx=5)
        self.btn_connect_b = ttk.Button(dev_b_frame, text="Connect", command=self.toggle_connect_b)
        self.btn_connect_b.pack(side="left")

        # Baud rate
        ttk.Label(conn_frame, text="Baud Rate:").pack(pady=(5, 0))
        self.baud_var = tk.IntVar(value=115200)
        self.baud_combo = ttk.Combobox(conn_frame, textvariable=self.baud_var, values=[9600, 19200, 38400, 57600, 115200, 250000, 500000, 921600, 1000000, 2000000], state="readonly", width=15)
        self.baud_combo.pack(pady=2)

        ttk.Button(conn_frame, text="Refresh Ports", command=self.refresh_ports).pack(pady=5)

        # --- Motion Control Section ---
        ctrl_frame = ttk.LabelFrame(self.scrollable_frame, text="Motion Control")
        ctrl_frame.pack(fill="x", padx=10, pady=5)

        # Speed
        ttk.Label(ctrl_frame, text="Speed (Hz):").pack(anchor="w", padx=5)
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_scale = ttk.Scale(ctrl_frame, from_=0.1, to=5.0, variable=self.speed_var, command=self.update_params)
        self.speed_scale.pack(fill="x", padx=5, pady=2)

        # Mode Selection
        mode_frame = ttk.Frame(ctrl_frame)
        mode_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(mode_frame, text="Motion Mode:").pack(side="left")
        self.mode_var = tk.StringVar(value="v_stroke")
        modes = [
            "v_stroke", "alternating_step", "wrapping_twist", "sole_rub",
            "toe_tease", "edge_stroking", "heel_press", "circling_tease",
            "wave_rub_up_down", "wave_rub_front_back", "static_rub_front_back", "asymmetric_sprint",
            "foot_slap", "glans_torture", "edging_sole_show",
            "single_foot_tease_left", "single_foot_tease_right",
            "single_foot_stroke_left", "single_foot_stroke_right"
        ]
        self.mode_combo = ttk.Combobox(mode_frame, textvariable=self.mode_var, values=modes, state="readonly")
        self.mode_combo.pack(side="left", padx=5)
        self.mode_combo.bind("<<ComboboxSelected>>", self.update_params)

        # Stroke / Base Squeeze (L0)
        ttk.Label(ctrl_frame, text="L0 Stroke Length (%):").pack(anchor="w", padx=5)
        self.stroke_var = tk.DoubleVar(value=50.0)
        self.stroke_scale = ttk.Scale(ctrl_frame, from_=0.0, to=100.0, variable=self.stroke_var, command=self.update_params)
        self.stroke_scale.pack(fill="x", padx=5, pady=2)

        ttk.Label(ctrl_frame, text="L0 Base Squeeze Offset (%):").pack(anchor="w", padx=5)
        self.base_squeeze_var = tk.DoubleVar(value=50.0)
        self.base_squeeze_scale = ttk.Scale(ctrl_frame, from_=0.0, to=100.0, variable=self.base_squeeze_var, command=self.update_params)
        self.base_squeeze_scale.pack(fill="x", padx=5, pady=2)

        # Advanced Axes
        adv_frame = ttk.LabelFrame(ctrl_frame, text="Advanced Axes (Depends on Mode)")
        adv_frame.pack(fill="x", padx=5, pady=5)

        # Ankle Pitch Offset (R2 Base)
        ttk.Label(adv_frame, text="Ankle Pitch Offset R2 Base (%):").pack(anchor="w", padx=5)
        self.ankle_offset_var = tk.DoubleVar(value=50.0)
        self.ankle_scale = ttk.Scale(adv_frame, from_=0.0, to=100.0, variable=self.ankle_offset_var, command=self.update_params)
        self.ankle_scale.pack(fill="x", padx=5, pady=2)

        # Ankle Roll Offset (R1 Base)
        ttk.Label(adv_frame, text="Ankle Roll Offset R1 Base (%):").pack(anchor="w", padx=5)
        self.roll_offset_var = tk.DoubleVar(value=50.0)
        self.roll_offset_scale = ttk.Scale(adv_frame, from_=0.0, to=100.0, variable=self.roll_offset_var, command=self.update_params)
        self.roll_offset_scale.pack(fill="x", padx=5, pady=2)

        # Pitch (R2)
        ttk.Label(adv_frame, text="Pitch Amplitude R2 (%):").pack(anchor="w", padx=5)
        self.pitch_amp_var = tk.DoubleVar(value=50.0)
        self.pitch_scale = ttk.Scale(adv_frame, from_=0.0, to=100.0, variable=self.pitch_amp_var, command=self.update_params)
        self.pitch_scale.pack(fill="x", padx=5, pady=2)

        # Roll (R1)
        ttk.Label(adv_frame, text="Roll Amplitude R1 (%):").pack(anchor="w", padx=5)
        self.roll_amp_var = tk.DoubleVar(value=50.0)
        self.roll_scale = ttk.Scale(adv_frame, from_=0.0, to=100.0, variable=self.roll_amp_var, command=self.update_params)
        self.roll_scale.pack(fill="x", padx=5, pady=2)

        # Twist (R0)
        ttk.Label(adv_frame, text="Twist Amplitude R0 (%):").pack(anchor="w", padx=5)
        self.twist_amp_var = tk.DoubleVar(value=50.0)
        self.twist_scale = ttk.Scale(adv_frame, from_=0.0, to=100.0, variable=self.twist_amp_var, command=self.update_params)
        self.twist_scale.pack(fill="x", padx=5, pady=2)

        # Tilt Compensation (L2 Offset)
        ttk.Label(adv_frame, text="Tilt Compensation L2 Base (%):").pack(anchor="w", padx=5)
        self.tilt_comp_var = tk.DoubleVar(value=0.0)
        self.tilt_comp_scale = ttk.Scale(adv_frame, from_=-100.0, to=100.0, variable=self.tilt_comp_var, command=self.update_params)
        self.tilt_comp_scale.pack(fill="x", padx=5, pady=2)

        self.reverse_l2_var = tk.BooleanVar(value=False)
        self.reverse_l2_check = ttk.Checkbutton(adv_frame, text="Reverse L2 Compensation Direction", variable=self.reverse_l2_var, command=self.update_params)
        self.reverse_l2_check.pack(anchor="w", padx=5, pady=5)
        # --- Calibration Section ---
        calib_frame = ttk.LabelFrame(self.scrollable_frame, text="Calibration & Initialization")
        calib_frame.pack(fill="x", padx=10, pady=5)

        self.btn_init = ttk.Button(calib_frame, text="INITIALIZE (Go to Neutral)", command=self.go_to_neutral)
        self.btn_init.pack(fill="x", padx=5, pady=5)

        ttk.Label(calib_frame, text="Height Offset A (L0):").pack(anchor="w", padx=5)
        self.height_offset_a_var = tk.DoubleVar(value=0.0)
        self.height_offset_a_scale = ttk.Scale(calib_frame, from_=-500, to=500, variable=self.height_offset_a_var, command=self.update_params)
        self.height_offset_a_scale.pack(fill="x", padx=5, pady=2)

        ttk.Label(calib_frame, text="Height Offset B (L0):").pack(anchor="w", padx=5)
        self.height_offset_b_var = tk.DoubleVar(value=0.0)
        self.height_offset_b_scale = ttk.Scale(calib_frame, from_=-500, to=500, variable=self.height_offset_b_var, command=self.update_params)
        self.height_offset_b_scale.pack(fill="x", padx=5, pady=2)

        # Start/Stop
        self.btn_start = ttk.Button(self.scrollable_frame, text="START MOTION", command=self.toggle_motion)
        self.btn_start.pack(fill="x", padx=20, pady=10, ipady=10)

        # --- Log Section ---
        log_frame = ttk.LabelFrame(self.scrollable_frame, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state='disabled')
        self.log_text.pack(fill="both", expand=True)

        # Setup custom logging handler
        self.log_handler = TextHandler(self.log_text)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))
        logger.addHandler(self.log_handler)

        self.refresh_ports()

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.combo_a['values'] = ports
        self.combo_b['values'] = ports
        if ports:
            if not self.port_a.get(): self.combo_a.current(0)
            if not self.port_b.get(): self.combo_b.current(0)

    def go_to_neutral(self):
        if self.controller.running:
            logger.warning("Stop motion before initializing")
            return
        self.controller.go_to_neutral()

    def _toggle_connect(self, device_id):
        is_connected = getattr(self.controller, f"connected_{device_id}")
        btn = getattr(self, f"btn_connect_{device_id}")
        port = getattr(self, f"port_{device_id}").get()
        baud = self.baud_var.get()

        if not is_connected:
            connect_method = getattr(self.controller, f"connect_device_{device_id}")
            if connect_method(port, baud):
                btn.config(text="Disconnect")
        else:
            ser = getattr(self.controller, f"ser_{device_id}")
            if ser:
                ser.close()
            setattr(self.controller, f"connected_{device_id}", False)
            btn.config(text="Connect")
            logger.info(f"Device {device_id.upper()} disconnected")

    def toggle_connect_a(self):
        self._toggle_connect('a')

    def toggle_connect_b(self):
        self._toggle_connect('b')

    def update_params(self, _=None):
        self.controller.speed = self.speed_var.get()
        self.controller.stroke = self.stroke_var.get()
        self.controller.base_squeeze = self.base_squeeze_var.get()
        self.controller.ankle_angle_offset = self.ankle_offset_var.get()
        self.controller.roll_angle_offset = self.roll_offset_var.get()
        self.controller.pitch_amp = self.pitch_amp_var.get()
        self.controller.roll_amp = self.roll_amp_var.get()
        self.controller.twist_amp = self.twist_amp_var.get()
        self.controller.reverse_l2 = self.reverse_l2_var.get()
        self.controller.tilt_compensation = self.tilt_comp_var.get()

        # Height Offsets
        self.controller.height_offset_a = int(self.height_offset_a_var.get())
        self.controller.height_offset_b = int(self.height_offset_b_var.get())

        # Update devices immediately if in initialization mode
        if getattr(self.controller, 'is_initializing', False) and not self.controller.running:
            self.controller.go_to_neutral()

        mode = self.mode_var.get()
        self.controller.motion_mode = mode

        # In some modes, we want synchronous base loops
        if mode in ["v_stroke", "wrapping_twist", "sole_rub", "edge_stroking", "heel_press", "circling_tease", "toe_tease",
                    "wave_rub_front_back", "static_rub_front_back", "asymmetric_sprint", "foot_slap", "glans_torture", "edging_sole_show",
                    "single_foot_tease_left", "single_foot_tease_right", "single_foot_stroke_left", "single_foot_stroke_right"]:
            self.controller.phase_shift = 0   # Base phase sync (modes handle mirroring internally if needed)
        else:
            self.controller.phase_shift = 180 # Base phase alternating (e.g. alternating_step)

    def toggle_motion(self):
        if not self.controller.running:
            if self.enable_ws.get():
                if not self.controller.ws_server_a:
                    self.controller.ws_server_a = TCodeWSServer(port=self.ws_port_a.get())
                if not self.controller.ws_server_b:
                    self.controller.ws_server_b = TCodeWSServer(port=self.ws_port_b.get())
                self.controller.ws_server_a.start()
                self.controller.ws_server_b.start()
            else:
                if self.controller.ws_server_a:
                    self.controller.ws_server_a.stop()
                    self.controller.ws_server_a = None
                if self.controller.ws_server_b:
                    self.controller.ws_server_b.stop()
                    self.controller.ws_server_b = None

            self.update_params() # Ensure latest params are set
            self.controller.start_motion()
            self.btn_start.config(text="STOP MOTION")
        else:
            self.controller.stop_motion()
            try:
                if self.controller.ws_server_a:
                    self.controller.ws_server_a.stop()
                    self.controller.ws_server_a = None
                if self.controller.ws_server_b:
                    self.controller.ws_server_b.stop()
                    self.controller.ws_server_b = None
            except Exception as e:
                logger.error(f"Error stopping WebSockets: {e}")
            self.btn_start.config(text="START MOTION")

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + "\n")
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        self.text_widget.after(0, append)

if __name__ == "__main__":
    root = tk.Tk()
    app = DualOSRGui(root)
    root.mainloop()
