import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time

class ESP32KeyboardController:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Keyboard Controller v2.0")
        self.root.geometry("600x500")
        
        self.serial_connection = None
        self.is_connected = False
        self.read_thread = None
        self.stop_reading = False
        
        self.setup_gui()
        self.refresh_ports()
        
    def setup_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        connection_frame = ttk.LabelFrame(main_frame, text="Connection", padding="5")
        connection_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        connection_frame.columnconfigure(1, weight=1)
        
        ttk.Label(connection_frame, text="COM Port:").grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(connection_frame, textvariable=self.port_var, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        self.refresh_btn = ttk.Button(connection_frame, text="Refresh", command=self.refresh_ports)
        self.refresh_btn.grid(row=0, column=2, padx=(0, 5))
        self.connect_btn = ttk.Button(connection_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=3)
        
        self.status_var = tk.StringVar(value="Disconnected")
        self.status_label = ttk.Label(connection_frame, textvariable=self.status_var, foreground="red")
        self.status_label.grid(row=1, column=0, columnspan=4, pady=(5, 0), sticky=tk.W)
        
        text_frame = ttk.LabelFrame(main_frame, text="Text to Type", padding="5")
        text_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.text_area = scrolledtext.ScrolledText(text_frame, height=10, wrap=tk.WORD)
        self.text_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=(0, 10), sticky=tk.W)
        self.type_btn = ttk.Button(button_frame, text="Start Typing", command=self.start_typing, state="disabled")
        self.type_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.stop_btn = ttk.Button(button_frame, text="Stop Typing", command=self.stop_typing, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.status_btn = ttk.Button(button_frame, text="Check Status", command=self.check_status, state="disabled")
        self.status_btn.pack(side=tk.LEFT)
        
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=8, state="disabled", wrap=tk.WORD)
        self.log_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        clear_log_btn = ttk.Button(main_frame, text="Clear Log", command=self.clear_log)
        clear_log_btn.grid(row=4, column=0, columnspan=3, pady=(5, 0), sticky=tk.E)
        
    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_names = [port.device for port in ports]
        self.port_combo['values'] = port_names
        if port_names: self.port_combo.set(port_names[0])
        else: self.port_var.set("")
        
    def toggle_connection(self):
        if not self.is_connected: self.connect()
        else: self.disconnect()
    
    def connect(self):
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port")
            return
        
        try:
            self.serial_connection = serial.Serial(port, 115200, timeout=1)
            self.log_message(f"Connecting to {port}, please wait...")
            self.root.update()
            time.sleep(2)
            
            self.is_connected = True
            self.status_var.set("Connected to " + port)
            self.status_label.configure(foreground="green")
            self.connect_btn.configure(text="Disconnect")
            
            self.type_btn.configure(state="normal")
            self.stop_btn.configure(state="normal")
            self.status_btn.configure(state="normal")
            
            self.stop_reading = False
            self.read_thread = threading.Thread(target=self.read_serial, daemon=True)
            self.read_thread.start()
            self.log_message("Connection successful.")
            
        except serial.SerialException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to {port}: {str(e)}")
            self.log_message("Connection failed.")
            
    def disconnect(self):
        if self.serial_connection:
            self.stop_reading = True
            if self.read_thread: self.read_thread.join(timeout=1)
            self.serial_connection.close()
            self.serial_connection = None
            
        self.is_connected = False
        self.status_var.set("Disconnected")
        self.status_label.configure(foreground="red")
        self.connect_btn.configure(text="Connect")
        
        self.type_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        self.status_btn.configure(state="disabled")
        
        self.log_message("Disconnected from ESP32")
    
    def read_serial(self):
        while not self.stop_reading and self.is_connected:
            try:
                if self.serial_connection and self.serial_connection.in_waiting:
                    data = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    if data: self.log_message(f"ESP32: {data}")
            except Exception as e:
                if not self.stop_reading: self.log_message(f"Serial port disconnected or read error.")
                self.root.after(0, self.disconnect)
                break
            time.sleep(0.1)
    
    def send_command(self, command_str):
        if self.serial_connection and self.is_connected:
            try:
                self.serial_connection.write(command_str.encode('utf-8'))
                return True
            except Exception as e:
                self.log_message(f"Send error: {str(e)}")
                self.disconnect()
                return False
        return False
    
    # =======================================================
    # ============= COMMAND SENDING LOGIC ===============
    # =======================================================
    def start_typing(self):
        """
        Initiates the typing process after a 5-second delay.
        """
        text = self.text_area.get("1.0", "end-1c")
        if not text:
            messagebox.showwarning("Warning", "Please enter some text to type")
            return

        # Log message and disable the button to prevent multiple clicks during the delay
        self.log_message("Request received. Typing will start in 5 seconds...")
        self.type_btn.configure(state="disabled")

        # Schedule the _execute_typing method to be called after 5000 ms (5 seconds)
        self.root.after(5000, self._execute_typing, text)

    def _execute_typing(self, text):
        """
        This function is called after the delay and sends the command to the ESP32.
        """
        # Re-enable the button now that the delay is over
        # We only re-enable it if the device is still connected
        if self.is_connected:
            self.type_btn.configure(state="normal")

        # Check if still connected before attempting to send the command
        if not self.is_connected:
            self.log_message("Typing cancelled. Disconnected during the delay.")
            messagebox.showwarning("Cancelled", "Typing was cancelled because the device was disconnected.")
            return

        # Encode text to get accurate byte length
        encoded_text = text.encode('utf-8')
        length = len(encoded_text)
        
        # Create the command in the new format: TYPE:<length>:<text>
        command = f"TYPE:{length}:{text}"
        
        self.log_message(f"Sending TYPE command with length {length}.")
        if not self.send_command(command):
            messagebox.showerror("Error", "Failed to send command to ESP32")

    def stop_typing(self):
        self.log_message("Sending STOP command.")
        self.send_command("STOP:") # Add delimiter for parser

    def check_status(self):
        self.log_message("Sending STATUS command.")
        self.send_command("STATUS:") # Add delimiter for parser

    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.root.after(0, self._update_log, log_entry)
    
    def _update_log(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, message)
        self.log_area.configure(state="disabled")
        self.log_area.see(tk.END)
    
    def clear_log(self):
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", tk.END)
        self.log_area.configure(state="disabled")
    
    def on_closing(self):
        if self.is_connected: self.disconnect()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ESP32KeyboardController(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()