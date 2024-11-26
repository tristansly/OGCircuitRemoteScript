from __future__ import absolute_import, print_function
import time
import Live
from ableton.v2.control_surface import ControlSurface, ButtonElement, EncoderElement, MIDI_CC_TYPE, MIDI_NOTE_TYPE
from _Framework.SessionComponent import SessionComponent, SceneComponent
from _Framework.ButtonMatrixElement import ButtonMatrixElement
from _Framework.SubjectSlot import subject_slot
from _Framework.ClipSlotComponent import ClipSlotComponent

# Move these outside the class
DEVICE_COLORS = {
    'color': '#FF5E00',  # Novation orange
    'color_type': 'rgb'
}

# Color definitions as class variable
COLORS = {
    'OFF': 0,
    'RED': 15,
    'RED_HALF': 13,
    'GREEN': 60,
    'GREEN_HALF': 28,
    'BLUE': 63,
    'BLUE_HALF': 46,
    'YELLOW': 62,
    'AMBER': 61,
    'PLAYING': 60,  # Bright green
    'TRIGGERED': 62,  # Yellow
    'STOPPED': 15,  # Red
    'RECORDING': 7,  # Bright red pulsing
    'EMPTY': 46,  # Dim blue
}

class Circuit(ControlSurface):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        with self.component_guard():
            self.log_message("Circuit Remote Script initializing...")
            self._modes = ["Session", "Mixer", "Effects"]
            self._mode_index = 0
            self._mode = self._modes[self._mode_index]
            self._is_idle = False
            self._led_state = {}
            self._idle_step = 0
            self._idle_task = None
            self._setup_controls()
            self._setup_mode_switcher()
            self.schedule_message(1000, self._start_idle_lightshow)
            self.log_message("Circuit Remote Script initialized successfully")
            self._setup_pad_matrix()
            self._setup_session()
            self._session.set_enabled(True)

    # --- Setup Section ---
    def _setup_controls(self):
        self._buttons = [ButtonElement(True, MIDI_NOTE_TYPE, 0, i) for i in range(36, 44)]
        for button in self._buttons:
            button.add_value_listener(self._exit_idle_mode)
        self._encoders = [EncoderElement(MIDI_CC_TYPE, 0, i, Live.MidiMap.MapMode.absolute) for i in range(21, 29)]
        self._brightness_knob = EncoderElement(MIDI_CC_TYPE, 0, 14, Live.MidiMap.MapMode.absolute)
        self._brightness_knob.add_value_listener(self._on_brightness_change)

    def _setup_mode_switcher(self):
        self._mode_switch_button = ButtonElement(True, MIDI_NOTE_TYPE, 0, 40)  # Mode button
        self._mode_switch_button.add_value_listener(self._on_mode_switch)

    # --- Mode Switching ---
    def _on_mode_switch(self, value):
        if value > 0:
            self.cancel_scheduled_messages(None)
            self._mode_index = (self._mode_index + 1) % len(self._modes)
            self._mode = self._modes[self._mode_index]
            self.log_message(f"Switched to mode: {self._mode}")
            self._update_mode_leds()
            self._apply_mode_settings()
            self.update_pads()

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
            self._session.set_enabled(True)
            self._map_buttons_to_clip_launch()
        else:
            self._session.set_enabled(False)
            # ... rest of mode settings ...

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
        self._idle_task = self.schedule_message(50, self._lightshow_step)

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

    def _exit_idle_mode(self, value):
        """Exit idle mode when any button is pressed"""
        if value > 0:
            self._is_idle = False
            if self._idle_task is not None:
                self.cancel_scheduled_messages(self._idle_task)
                self._idle_task = None
            self._update_mode_leds()  # Restore normal LED state

    def disconnect(self):
        """Clean up when disconnecting"""
        self._is_idle = False
        if self._idle_task is not None:
            self.cancel_scheduled_messages(self._idle_task)
        
        # Remove all listeners
        for button in self._buttons:
            button.remove_value_listener(self._exit_idle_mode)
        self._brightness_knob.remove_value_listener(self._on_brightness_change)
        
        # Remove clip slot listeners
        for scene_index in range(2):
            scene = self._session.scene(scene_index)
            for slot_index in range(4):
                slot = scene.clip_slot(slot_index)
                slot.remove_has_clip_listener(self._on_clip_state_change)
                slot.remove_playing_status_listener(self._on_clip_state_change)
                slot.remove_is_recording_listener(self._on_clip_state_change)
        
        super().disconnect()

    def _setup_pad_matrix(self):
        """Setup the pad matrix for lighting and clip launching"""
        self._pad_matrix = ButtonMatrixElement(rows=[
            [ButtonElement(True, MIDI_NOTE_TYPE, 0, 36 + (row * 4) + col) 
             for col in range(4)] 
            for row in range(2)
        ])
        self._pad_colors = [[COLORS['OFF'] for x in range(4)] for y in range(2)]
        self.update_pads()  # Initial pad update
        
    def _setup_session(self):
        """Setup session component for clip launching"""
        # Create a session with scene offset to match Live's view
        self._session = SessionComponent(
            num_tracks=4,
            num_scenes=2,
            name='Session_Control',
            is_enabled=True,
            enable_skinning=True
        )
        
        # Set up the session grid
        self._scene_launch_buttons = []
        self._track_stop_buttons = []
        
        # Create the button matrix
        self._pad_matrix = ButtonMatrixElement(rows=[
            [ButtonElement(True, MIDI_NOTE_TYPE, 0, 36 + (row * 4) + col) 
             for col in range(4)] 
            for row in range(2)
        ])
        
        # Bind matrix to session
        self._session.set_matrix(self._pad_matrix)
        
        # Set up session navigation
        self._session.set_track_bank_left_button(ButtonElement(True, MIDI_NOTE_TYPE, 0, 44))
        self._session.set_track_bank_right_button(ButtonElement(True, MIDI_NOTE_TYPE, 0, 45))
        self._session.set_scene_bank_up_button(ButtonElement(True, MIDI_NOTE_TYPE, 0, 46))
        self._session.set_scene_bank_down_button(ButtonElement(True, MIDI_NOTE_TYPE, 0, 47))
        
        # Enable session highlighting (colored box in Live)
        self.set_highlighting_session_component(self._session)
        self._session.set_rgb_mode(True)  # Enable RGB mode if available
        
        # Set initial position to track 0, scene 0
        self._session.set_offsets(0, 0)
        
        # Add clip state listeners
        for scene_index in range(2):
            for track_index in range(4):
                clip_slot = self._session.scene(scene_index).clip_slot(track_index)
                clip_slot.add_has_clip_listener(self._on_clip_state_change)
                clip_slot.add_playing_status_listener(self._on_clip_state_change)
                clip_slot.add_is_recording_listener(self._on_clip_state_change)

    @subject_slot('value')
    def _on_clip_state_change(self):
        """Handle clip state changes with smooth transitions"""
        if not self._mode == "Session":
            return
        for row in range(2):
            for col in range(4):
                clip_slot = self._session.scene(row).clip_slot(col)
                if clip_slot:  # Check if slot exists
                    target_color = self._get_clip_color(clip_slot)
                    note = 36 + (row * 4) + col
                    self._interpolate_color(note, self._color_to_rgb(target_color), duration=0.2)

    def _get_clip_color(self, clip_slot):
        """Determine the appropriate color based on clip slot state"""
        if clip_slot.is_recording:
            return COLORS['RECORDING']
        elif clip_slot.has_clip:
            if clip_slot.is_playing:
                return COLORS['PLAYING']
            elif clip_slot.is_triggered:
                return COLORS['TRIGGERED']
            else:
                return COLORS['STOPPED']
        else:
            return COLORS['EMPTY']

    def _color_to_rgb(self, color_index):
        """Convert color index to RGB values"""
        # This is a basic conversion - adjust these values based on your hardware
        color_map = {
            COLORS['PLAYING']: [0, 127, 0],    # Bright green
            COLORS['TRIGGERED']: [127, 127, 0], # Yellow
            COLORS['STOPPED']: [127, 0, 0],     # Red
            COLORS['RECORDING']: [127, 0, 0],   # Bright red
            COLORS['EMPTY']: [0, 0, 64],        # Dim blue
        }
        return color_map.get(color_index, [0, 0, 0])

    def _map_buttons_to_clip_launch(self):
        """Map pads to clip launching in Session mode"""
        for row in range(2):
            for col in range(4):
                button = self._pad_matrix.get_button(row, col)
                clip_slot = self._session.scene(row).clip_slot(col)
                
                # Update pad color based on clip state
                if clip_slot.has_clip:
                    self.light_pad(row, col, COLORS['GREEN'])  # Has clip
                elif clip_slot.controls_other_clips:
                    self.light_pad(row, col, COLORS['AMBER'])  # Stop button
                else:
                    self.light_pad(row, col, COLORS['BLUE_HALF'])  # Empty slot

    def light_pad(self, row, col, color):
        """Light a specific pad"""
        if 0 <= row < 2 and 0 <= col < 4:  # Bounds checking
            note = 36 + (row * 4) + col  # Adjust based on Circuit's MIDI mapping
            self._send_midi((0x90, note, color))  # MIDI Note On message
            self._pad_colors[row][col] = color
            
    def update_pads(self):
        """Update all pads based on current mode"""
        if self._mode == "Session":
            self._map_buttons_to_clip_launch()
        elif self._mode == "Mixer":
            for row in range(2):
                for col in range(4):
                    self.light_pad(row, col, COLORS['GREEN'])
        elif self._mode == "Effects":
            for row in range(2):
                for col in range(4):
                    self.light_pad(row, col, COLORS['RED'])

    def refresh_state(self):
        """Called by Live when the script needs to refresh its state"""
        super().refresh_state()
        self._update_mode_leds()
        if self._mode == "Session":
            self._map_buttons_to_clip_launch()
