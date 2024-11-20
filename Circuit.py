from __future__ import absolute_import, print_function
import time
from ableton.v2.control_surface import ControlSurface, ButtonElement, EncoderElement, MIDI_CC_TYPE, MIDI_NOTE_TYPE


class Circuit(ControlSurface):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._modes = ["Session", "Mixer", "Effects"]
        self._mode_index = 0
        self._mode = self._modes[self._mode_index]
        self._is_idle = False
        self._led_state = {}
        self._idle_step = 0
        self._setup_controls()
        self._setup_mode_switcher()
        self.schedule_message(1000, self._start_idle_lightshow)  # Auto-idle after 1000ms of no input

    # --- Setup Section ---
    def _setup_controls(self):
        self._buttons = [ButtonElement(True, MIDI_NOTE_TYPE, 0, i) for i in range(36, 44)]
        self._encoders = [EncoderElement(MIDI_CC_TYPE, 0, i, Live.MidiMap.MapMode.absolute) for i in range(21, 29)]
        self._brightness_knob = EncoderElement(MIDI_CC_TYPE, 0, 14, Live.MidiMap.MapMode.absolute)
        self._brightness_knob.add_value_listener(self._on_brightness_change)

    def _setup_mode_switcher(self):
        self._mode_switch_button = ButtonElement(True, MIDI_NOTE_TYPE, 0, 40)  # Mode button
        self._mode_switch_button.add_value_listener(self._on_mode_switch)

    # --- Mode Switching ---
    def _on_mode_switch(self, value):
        if value > 0:
            self._mode_index = (self._mode_index + 1) % len(self._modes)
            self._mode = self._modes[self._mode_index]
            self.log_message(f"Switched to mode: {self._mode}")
            self._update_mode_leds()
            self._apply_mode_settings()

    def _update_mode_leds(self):
        colors = {
            "Session": [127, 0, 127],  # Purple
            "Mixer": [0, 127, 127],    # Cyan
            "Effects": [127, 127, 0],  # Yellow
        }
        self._interpolate_color(40, colors[self._mode], duration=1.0)

    def _apply_mode_settings(self):
        """Adjust control mappings and LED behaviors for the selected mode."""
        if self._mode == "Session":
            self._map_buttons_to_clip_launch()
        elif self._mode == "Mixer":
            self._map_knobs_to_volume_pan()
        elif self._mode == "Effects":
            self._map_knobs_to_device_controls()

    # --- LED Animations ---
    def _start_idle_lightshow(self):
        self._is_idle = True
        self._lightshow_step()

    def _lightshow_step(self):
        if not self._is_idle:
            return

        for note in self._led_state.keys():
            offset = (note + self._idle_step) % 50
            rainbow_color = [
                (offset * 5) % 127,
                (offset * 3) % 127,
                (offset * 7) % 127,
            ]
            self._interpolate_color(note, rainbow_color, duration=0.5, steps=10)

        self._idle_step += 1
        self.schedule_message(50, self._lightshow_step)  # Repeat after 50ms

    # --- Knob-Controlled LED Brightness ---
    def _on_brightness_change(self, value):
        brightness = int(value * 127 / 127)  # Map to brightness range
        for note in self._led_state.keys():
            current_color = self._led_state[note]
            adjusted_color = [int(c * brightness / 127) for c in current_color]
            self._send_led_color(note, adjusted_color)

    # --- Utility Functions ---
    def _send_led_color(self, note, color):
        """Send color to LED via MIDI."""
        self._led_state[note] = color
        velocity = (color[0] & 0xF) << 4 | (color[1] & 0xF)  # Pack R and G
        self._send_midi([0x90, note, velocity])
        self._send_midi([0x92, note, color[2]])  # Separate B channel if needed

    def _interpolate_color(self, note, target_color, duration=0.5, steps=20):
        """
        Smoothly interpolate LED color to the target value.
        :param note: The MIDI note associated with the LED.
        :param target_color: The target RGB color as [R, G, B].
        :param duration: Total duration of the interpolation in seconds.
        :param steps: Number of steps for the interpolation.
        """
        if note not in self._led_state:
            self._led_state[note] = [0, 0, 0]  # Default color if not set

        current_color = self._led_state[note]
        step_delay = duration / steps

        for step in range(steps + 1):  # Include the target step
            interpolated_color = [
                int(current_color[i] + (target_color[i] - current_color[i]) * (step / steps))
                for i in range(3)
            ]
            self.schedule_message(int(step * step_delay * 1000), self._send_led_color, note, interpolated_color)
