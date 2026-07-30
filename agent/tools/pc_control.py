"""
NexAlfa PC Control & Diagnostics
System info, OS settings, camera, audio devices, Wi-Fi, Bluetooth, power management.
All powered by PowerShell/WMI on Windows — no extra native deps needed (except opencv for camera).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Optional

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.pc")


async def _ps(cmd: str, timeout: int = 15) -> str:
    """Run a PowerShell command and return output."""
    proc = await asyncio.create_subprocess_exec(
        "powershell", "-NoProfile", "-Command", cmd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    out = stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0 and stderr:
        out += f"\n[error] {stderr.decode('utf-8', errors='replace').strip()}"
    return out


# ═══════════════════════════════════════════════════════════════
#  SYSTEM INFO & DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════

class PcSystemInfoTool(Tool):
    name = "pc_system_info"
    description = (
        "Get full hardware/software specs: CPU, RAM, GPU, disk, OS, battery, screen. "
        "Use this to answer questions like 'can my laptop run X?' or 'how much RAM do I have?'"
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self) -> str:
        try:
            parts = []
            # CPU
            cpu = await _ps("Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json")
            parts.append(f"**CPU**: {cpu}")
            # RAM
            ram = await _ps("$r=Get-CimInstance Win32_PhysicalMemory|Measure-Object Capacity -Sum; [math]::Round($r.Sum/1GB,1)")
            parts.append(f"**RAM**: {ram} GB")
            # GPU
            gpu = await _ps("Get-CimInstance Win32_VideoController | Select-Object Name,@{N='VRAM_GB';E={[math]::Round($_.AdapterRAM/1GB,1)}} | ConvertTo-Json")
            parts.append(f"**GPU**: {gpu}")
            # Disk
            disk = await _ps("Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,@{N='Size_GB';E={[math]::Round($_.Size/1GB,1)}},@{N='Free_GB';E={[math]::Round($_.FreeSpace/1GB,1)}} | ConvertTo-Json")
            parts.append(f"**Disk**: {disk}")
            # OS
            osinfo = await _ps("Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture | ConvertTo-Json")
            parts.append(f"**OS**: {osinfo}")
            # Battery
            bat = await _ps("Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining,BatteryStatus | ConvertTo-Json")
            if bat and "No instances" not in bat:
                parts.append(f"**Battery**: {bat}")
            else:
                parts.append("**Battery**: Desktop (no battery)")
            # Screen
            scr = await _ps("Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { \"$($_.DeviceName): $($_.Bounds.Width)x$($_.Bounds.Height)\" }")
            parts.append(f"**Display**: {scr}")
            return "\n".join(parts)
        except Exception as e:
            return f"Error: {e}"


class PcRunningProcessesTool(Tool):
    name = "pc_running_processes"
    description = "List running processes sorted by CPU or memory usage, or kill a process by name/PID."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "sort_by": {"type": "string", "enum": ["cpu", "memory", "name"], "description": "Sort order (default: memory)."},
                    "top": {"type": "integer", "description": "Show top N processes (default: 15)."},
                    "kill": {"type": "string", "description": "Process name or PID to kill (optional)."},
                },
                "required": [],
            },
        }

    async def execute(self, sort_by: str = "memory", top: int = 15, kill: str = None) -> str:
        try:
            if kill:
                result = await _ps(f"Stop-Process -Name '{kill}' -Force -ErrorAction SilentlyContinue; Stop-Process -Id {kill} -Force -ErrorAction SilentlyContinue; echo 'Done'")
                return f"Kill signal sent to '{kill}': {result}"
            sort_prop = "WorkingSet64" if sort_by == "memory" else ("CPU" if sort_by == "cpu" else "ProcessName")
            result = await _ps(
                f"Get-Process | Sort-Object {sort_prop} -Descending | Select-Object -First {top} "
                f"ProcessName,Id,@{{N='CPU_s';E={{[math]::Round($_.CPU,1)}}}},@{{N='RAM_MB';E={{[math]::Round($_.WorkingSet64/1MB,1)}}}} "
                f"| Format-Table -AutoSize | Out-String"
            )
            return result
        except Exception as e:
            return f"Error: {e}"


class PcNetworkInfoTool(Tool):
    name = "pc_network_info"
    description = "Get network info: IP addresses, Wi-Fi status, connected network, signal strength."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self) -> str:
        try:
            parts = []
            ip = await _ps("Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'} | Select-Object InterfaceAlias,IPAddress | Format-Table -AutoSize | Out-String")
            parts.append(f"**IP Addresses**:\n{ip}")
            wifi = await _ps("netsh wlan show interfaces")
            parts.append(f"**Wi-Fi**:\n{wifi}")
            return "\n".join(parts)
        except Exception as e:
            return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  OS SETTINGS
# ═══════════════════════════════════════════════════════════════

class PcSetWallpaperTool(Tool):
    name = "pc_set_wallpaper"
    description = "Change the desktop wallpaper from a local file path or a solid color."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to image file for wallpaper."},
                    "color": {"type": "string", "description": "Solid color hex (e.g. '#000000' for black). Used if no path given."},
                },
                "required": [],
            },
        }

    async def execute(self, path: str = None, color: str = None) -> str:
        try:
            if path:
                p = str(Path(path).expanduser().resolve())
                ps_cmd = f"""
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public class Wallpaper {{
    [DllImport("user32.dll", CharSet=CharSet.Auto)]
    public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
}}
'@
[Wallpaper]::SystemParametersInfo(0x0014, 0, "{p}", 0x01 -bor 0x02)
"""
                await _ps(ps_cmd)
                return f"Wallpaper set to: {p}"
            elif color:
                # Create solid color image and set it
                from PIL import Image
                hex_c = color.lstrip('#')
                rgb = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
                img = Image.new('RGB', (1920, 1080), rgb)
                wp_path = Path("storage/wallpaper_solid.bmp").resolve()
                wp_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(str(wp_path), "BMP")
                return await self.execute(path=str(wp_path))
            return "Provide either 'path' to an image or 'color' hex code."
        except Exception as e:
            return f"Error: {e}"


class PcSetDarkModeTool(Tool):
    name = "pc_set_dark_mode"
    description = "Toggle Windows dark/light mode for apps and system."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "description": "true = dark mode, false = light mode."},
                },
                "required": ["enabled"],
            },
        }

    async def execute(self, enabled: bool = True) -> str:
        try:
            val = 0 if enabled else 1
            await _ps(f"Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' -Value {val}")
            await _ps(f"Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' -Value {val}")
            return f"{'Dark' if enabled else 'Light'} mode activated."
        except Exception as e:
            return f"Error: {e}"


class PcSetVolumeTool(Tool):
    name = "pc_set_volume"
    description = "Get or set system volume (0-100), or mute/unmute."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Volume level 0-100."},
                    "mute": {"type": "boolean", "description": "true=mute, false=unmute."},
                    "get": {"type": "boolean", "description": "Just get current volume without changing."},
                },
                "required": [],
            },
        }

    async def execute(self, level: int = None, mute: bool = None, get: bool = False) -> str:
        try:
            if get or (level is None and mute is None):
                result = await _ps(
                    "Add-Type -TypeDefinition @'\n"
                    "using System.Runtime.InteropServices;\n"
                    "[Guid(\"5CDF2C82-841E-4546-9722-0CF74078229A\"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]\n"
                    "interface IAudioEndpointVolume { int _0(); int _1(); int _2(); int _3();\n"
                    "int GetMasterVolumeLevelScalar(out float level); }\n"
                    "'@ -ErrorAction SilentlyContinue\n"
                    "echo 'Use nircmd or volume keys for reliable volume control on Windows.'"
                )
                return f"Volume info: Use desktop_hotkey with volume keys for control. Current state: check system tray."
            if mute is not None:
                # Use nircmd-style approach via SendKeys
                await _ps("$w=New-Object -ComObject WScript.Shell; $w.SendKeys([char]173)")
                return "Mute toggled."
            if level is not None:
                # Set volume via PowerShell + nircmd or key simulation
                steps = int(level / 2)  # Volume up/down keys change by 2%
                await _ps("$w=New-Object -ComObject WScript.Shell; " + "; ".join(["$w.SendKeys([char]174)"] * 50))  # First mute all
                await _ps("$w=New-Object -ComObject WScript.Shell; " + "; ".join(["$w.SendKeys([char]175)"] * steps))
                return f"Volume set to approximately {level}%."
        except Exception as e:
            return f"Error: {e}"


class PcDisplaySettingsTool(Tool):
    name = "pc_display_settings"
    description = "Get display info: resolution, refresh rate, brightness. Can set brightness."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "brightness": {"type": "integer", "description": "Set brightness 0-100 (laptop only)."},
                },
                "required": [],
            },
        }

    async def execute(self, brightness: int = None) -> str:
        try:
            if brightness is not None:
                await _ps(f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{brightness})")
                return f"Brightness set to {brightness}%."
            result = await _ps(
                "Get-CimInstance Win32_VideoController | Select-Object Name,VideoModeDescription,CurrentRefreshRate | Format-List | Out-String"
            )
            bri = await _ps("(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness")
            return f"{result}\nBrightness: {bri}%" if bri else result
        except Exception as e:
            return f"Error: {e}"


class PcWifiControlTool(Tool):
    name = "pc_wifi_control"
    description = "List available Wi-Fi networks, connect to a network, or disconnect."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "connect", "disconnect", "status"], "description": "Action to perform."},
                    "network": {"type": "string", "description": "Network name (SSID) to connect to."},
                },
                "required": ["action"],
            },
        }

    async def execute(self, action: str, network: str = None) -> str:
        try:
            if action == "list":
                return await _ps("netsh wlan show networks mode=Bssid")
            elif action == "connect" and network:
                return await _ps(f'netsh wlan connect name="{network}"')
            elif action == "disconnect":
                return await _ps("netsh wlan disconnect")
            elif action == "status":
                return await _ps("netsh wlan show interfaces")
            return "Specify action: list, connect, disconnect, or status."
        except Exception as e:
            return f"Error: {e}"


class PcBluetoothControlTool(Tool):
    name = "pc_bluetooth_control"
    description = "Enable/disable Bluetooth or list paired devices."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "enable", "disable", "devices"], "description": "Action."},
                },
                "required": ["action"],
            },
        }

    async def execute(self, action: str) -> str:
        try:
            if action == "devices":
                return await _ps("Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status | Format-Table -AutoSize | Out-String")
            elif action == "status":
                return await _ps("Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Select-Object FriendlyName,Status | Format-Table | Out-String")
            elif action in ("enable", "disable"):
                return await _ps(f'Get-PnpDevice -Class Bluetooth | ForEach-Object {{ {"Enable" if action == "enable" else "Disable"}-PnpDevice -InstanceId $_.InstanceId -Confirm:$false }}')
            return "Specify action: status, enable, disable, devices."
        except Exception as e:
            return f"Error: {e}"


class PcPowerSettingsTool(Tool):
    name = "pc_power_settings"
    description = "Battery status, power plan, or shutdown/restart/lock/sleep the PC."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "lock", "sleep", "shutdown", "restart"],
                        "description": "Action to perform. Use 'status' to check battery/power plan.",
                    },
                },
                "required": ["action"],
            },
        }

    async def execute(self, action: str) -> str:
        try:
            if action == "status":
                bat = await _ps("Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining,BatteryStatus,EstimatedRunTime | ConvertTo-Json")
                plan = await _ps("powercfg /getactivescheme")
                return f"**Battery**: {bat}\n**Power Plan**: {plan}"
            elif action == "lock":
                await _ps("rundll32.exe user32.dll,LockWorkStation")
                return "PC locked."
            elif action == "sleep":
                await _ps("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                return "PC entering sleep mode."
            elif action == "shutdown":
                return "⚠️ Shutdown requested. Run `shutdown /s /t 30` via shell tool to confirm (30s delay to cancel)."
            elif action == "restart":
                return "⚠️ Restart requested. Run `shutdown /r /t 30` via shell tool to confirm (30s delay to cancel)."
            return "Unknown action."
        except Exception as e:
            return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  CAMERA & AUDIO DEVICES
# ═══════════════════════════════════════════════════════════════

# Permission flags — user can toggle these
_permissions = {
    "camera": False,
    "microphone": False,
    "speakers": True,  # speakers are generally safe
}

def set_device_permission(device: str, allowed: bool):
    """Toggle permission for camera/microphone/speakers."""
    if device in _permissions:
        _permissions[device] = allowed


class PcCameraCaptureTool(Tool):
    name = "pc_camera_capture"
    description = (
        "Take a photo using the webcam (built-in or USB). "
        "Requires camera permission to be enabled. Returns base64 image."
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "camera_index": {"type": "integer", "description": "Camera device index (default: 0 = primary)."},
                    "save_path": {"type": "string", "description": "Optional path to save the photo."},
                },
                "required": [],
            },
        }

    async def execute(self, camera_index: int = 0, save_path: str = None) -> str:
        if not _permissions.get("camera"):
            return "❌ Camera permission denied. Ask the user to enable it: 'enable camera access for Nex'."
        try:
            import cv2
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                return f"Error: Cannot open camera {camera_index}."
            # Warm up and capture
            for _ in range(5):
                cap.read()
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return "Error: Failed to capture frame."
            # Convert to base64
            _, buf = cv2.imencode('.png', frame)
            b64 = base64.b64encode(buf).decode('utf-8')
            h, w = frame.shape[:2]
            if save_path:
                p = Path(save_path).expanduser()
                p.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(p), frame)
            return f"Photo captured ({w}x{h}). [IMAGE:data:image/png;base64,{b64}]"
        except ImportError:
            return "Error: opencv-python not installed. Run: pip install opencv-python"
        except Exception as e:
            return f"Error: {e}"


class PcListDevicesTool(Tool):
    name = "pc_list_devices"
    description = "List audio devices (speakers, microphones) and cameras connected to the PC."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["audio", "camera", "all"], "description": "Device type to list."},
                },
                "required": [],
            },
        }

    async def execute(self, type: str = "all") -> str:
        try:
            parts = []
            if type in ("audio", "all"):
                audio = await _ps("Get-CimInstance Win32_SoundDevice | Select-Object Name,Status | Format-Table -AutoSize | Out-String")
                parts.append(f"**Audio Devices**:\n{audio}")
                endpoints = await _ps(
                    "Get-CimInstance -Namespace root/cimv2 -ClassName Win32_PnPEntity | "
                    "Where-Object { $_.PNPClass -eq 'AudioEndpoint' -or $_.PNPClass -eq 'MEDIA' } | "
                    "Select-Object Name,Status | Format-Table -AutoSize | Out-String"
                )
                if endpoints.strip():
                    parts.append(f"**Audio Endpoints**:\n{endpoints}")
            if type in ("camera", "all"):
                cams = await _ps(
                    "Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image' } | "
                    "Select-Object Name,Status | Format-Table -AutoSize | Out-String"
                )
                parts.append(f"**Cameras**:\n{cams if cams.strip() else 'No cameras found.'}")
            # Show permission status
            parts.append(f"\n**Permissions**: Camera={'✅ ON' if _permissions['camera'] else '❌ OFF'}, "
                        f"Microphone={'✅ ON' if _permissions['microphone'] else '❌ OFF'}, "
                        f"Speakers={'✅ ON' if _permissions['speakers'] else '❌ OFF'}")
            return "\n".join(parts)
        except Exception as e:
            return f"Error: {e}"


class PcTogglePermissionTool(Tool):
    name = "pc_toggle_permission"
    description = (
        "Enable or disable Nex's access to camera, microphone, or speakers. "
        "Like Windows OS permission toggles. Must be explicitly granted by the user."
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {"type": "string", "enum": ["camera", "microphone", "speakers"], "description": "Device type."},
                    "enabled": {"type": "boolean", "description": "true = allow, false = deny."},
                },
                "required": ["device", "enabled"],
            },
        }

    async def execute(self, device: str, enabled: bool) -> str:
        set_device_permission(device, enabled)
        status = "✅ ENABLED" if enabled else "❌ DISABLED"
        return f"{device.capitalize()} access: {status}"


class PcRecordAudioTool(Tool):
    name = "pc_record_audio"
    description = "Record audio from the microphone for a specified duration. Requires microphone permission."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {"type": "integer", "description": "Recording duration in seconds (max 60)."},
                    "save_path": {"type": "string", "description": "Path to save the audio file (WAV)."},
                },
                "required": ["duration", "save_path"],
            },
        }

    async def execute(self, duration: int, save_path: str) -> str:
        if not _permissions.get("microphone"):
            return "❌ Microphone permission denied. Ask the user to enable it first."
        duration = min(duration, 60)
        try:
            # Use PowerShell + .NET to record
            p = str(Path(save_path).expanduser().resolve())
            ps_cmd = f"""
Add-Type -AssemblyName System.Speech
$r = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$r.SetInputToDefaultAudioDevice()
# Use ffmpeg if available, else fallback
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpeg) {{
    & ffmpeg -f dshow -i audio="Microphone" -t {duration} -y "{p}" 2>$null
    echo "Recorded {duration}s to {p}"
}} else {{
    echo "FFmpeg not found. Install FFmpeg for audio recording."
}}
"""
            result = await _ps(ps_cmd, timeout=duration + 10)
            return result
        except Exception as e:
            return f"Error: {e}"


class PcPlayAudioTool(Tool):
    name = "pc_play_audio"
    description = "Play an audio file through the speakers."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to audio file (WAV, MP3, etc.)."},
                },
                "required": ["path"],
            },
        }

    async def execute(self, path: str) -> str:
        if not _permissions.get("speakers"):
            return "❌ Speaker access denied."
        try:
            p = str(Path(path).expanduser().resolve())
            if not Path(p).exists():
                return f"File not found: {p}"
            await _ps(f'(New-Object Media.SoundPlayer "{p}").PlaySync()', timeout=30)
            return f"Played: {p}"
        except Exception as e:
            return f"Error: {e}"


# ── Export ────────────────────────────────────────────────────

def get_pc_control_tools() -> list[Tool]:
    tools = [
        PcSystemInfoTool(),
        PcRunningProcessesTool(),
        PcNetworkInfoTool(),
        PcSetWallpaperTool(),
        PcSetDarkModeTool(),
        PcSetVolumeTool(),
        PcDisplaySettingsTool(),
        PcWifiControlTool(),
        PcBluetoothControlTool(),
        PcPowerSettingsTool(),
        PcCameraCaptureTool(),
        PcListDevicesTool(),
        PcTogglePermissionTool(),
        PcRecordAudioTool(),
        PcPlayAudioTool(),
    ]
    for t in tools:
        t.category = "pc_control"
    return tools
