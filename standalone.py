import rtmidi
import time
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CircuitDevice:
    midi_in: rtmidi.MidiIn
    midi_out: rtmidi.MidiOut
    in_port_name: str
    out_port_name: str

class CircuitController:
    def __init__(self):
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()
        self.device: Optional[CircuitDevice] = None
        
        # Color definitions
        self.COLORS = {
            'OFF': 0,
            'RED': 15,
            'GREEN': 60,
            'BLUE': 63,
            'YELLOW': 62,
        }

    def find_circuit(self) -> bool:
        """Find and connect to the Novation Circuit"""
        in_ports = self.midi_in.get_ports()
        out_ports = self.midi_out.get_ports()
        
        circuit_in = None
        circuit_out = None
        
        # Look for Circuit in port names
        for i, port in enumerate(in_ports):
            if 'Circuit' in port:
                circuit_in = (i, port)
                
        for i, port in enumerate(out_ports):
            if 'Circuit' in port:
                circuit_out = (i, port)
                
        if circuit_in and circuit_out:
            self.midi_in.open_port(circuit_in[0])
            self.midi_out.open_port(circuit_out[0])
            self.device = CircuitDevice(
                self.midi_in,
                self.midi_out,
                circuit_in[1],
                circuit_out[1]
            )
            return True
            
        return False

    def light_pad(self, pad: int, color: int):
        """Light a specific pad with a color"""
        if not self.device:
            return
        # MIDI Note On message
        self.device.midi_out.send_message([0x90, pad, color])

    def set_rgb_pad(self, pad: int, r: int, g: int, b: int):
        """Set RGB color for a pad"""
        if not self.device:
            return
        velocity = (r & 0xF) << 4 | (g & 0xF)  # Pack R and G
        self.device.midi_out.send_message([0x90, pad, velocity])
        self.device.midi_out.send_message([0x92, pad, b])  # Blue channel

    def start_midi_callback(self):
        """Start listening for MIDI input"""
        def midi_callback(message, time_stamp):
            msg_type = message[0] & 0xF0
            channel = message[0] & 0x0F
            note = message[1]
            velocity = message[2]
            print(f"MIDI Message - Type: {msg_type}, Channel: {channel}, Note: {note}, Velocity: {velocity}")
            
        self.device.midi_in.set_callback(midi_callback)

    def rainbow_demo(self):
        """Demo showing rainbow animation across pads"""
        if not self.device:
            return
            
        print("Running rainbow demo... Press Ctrl+C to stop")
        try:
            step = 0
            while True:
                for note in range(36, 44):  # Circuit's pad range
                    offset = (note + step) % 50
                    r = (offset * 5) % 16
                    g = (offset * 3) % 16
                    b = (offset * 7) % 16
                    self.set_rgb_pad(note, r, g, b)
                step += 1
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\nStopping demo")
            # Turn off all pads
            for note in range(36, 44):
                self.light_pad(note, self.COLORS['OFF'])

def main():
    controller = CircuitController()
    
    print("Looking for Novation Circuit...")
    if controller.find_circuit():
        print(f"Connected to Circuit!")
        print(f"Input: {controller.device.in_port_name}")
        print(f"Output: {controller.device.out_port_name}")
        
        # Start MIDI callback
        controller.start_midi_callback()
        
        # Run demo
        controller.rainbow_demo()
    else:
        print("No Circuit found! Please check connections.")

if __name__ == "__main__":
    main()