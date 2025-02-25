import tkinter as tk
from tkinter import ttk
import psutil
import cpuinfo
import platform
import os
import math
import time
import ctypes
from collections import deque
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Attempt to load the overclocking shared library (compiled from your C code)
try:
    oc_lib = ctypes.CDLL('./overclock.so')
    # Set function signature: set_cpu_multiplier(core, multiplier)
    oc_lib.set_cpu_multiplier.argtypes = [ctypes.c_int, ctypes.c_int]
except Exception as e:
    print("Overclock library not found:", e)
    oc_lib = None

def get_motherboard_info():
    os_name = platform.system()
    try:
        if os_name == "Windows":
            import wmi
            w = wmi.WMI()
            for board in w.Win32_BaseBoard():
                return f"{board.Manufacturer} {board.Product}".strip()
        elif os_name == "Linux":
            vendor = product = "Unknown"
            with open('/sys/class/dmi/id/board_vendor', 'r') as f:
                vendor = f.read().strip()
            with open('/sys/class/dmi/id/board_name', 'r') as f:
                product = f.read().strip()
            return f"{vendor} {product}"
        else:
            return "Unsupported OS"
    except Exception as e:
        return "Unavailable"

def get_system_info():
    info = {}
    cpu = cpuinfo.get_cpu_info()
    mem = psutil.virtual_memory()
    
    info['cpu'] = {
        'name': cpu.get('brand_raw', 'Unknown'),
        'arch': cpu.get('arch_string_raw', 'Unknown'),
        'cores': psutil.cpu_count(logical=False),
        'threads': psutil.cpu_count(logical=True),
        'freq': psutil.cpu_freq().current if psutil.cpu_freq() else None
    }
    
    info['system'] = {
        'os': f"{platform.system()} {platform.release()}",
        'version': platform.version(),
        'memory': {
            'total': mem.total // (1024**3),
            'available': mem.available // (1024**3)
        }
    }
    
    info['motherboard'] = get_motherboard_info()
    return info

class OverclockingGUI:
    def __init__(self, master):
        self.master = master
        self.system_info = get_system_info()
        self.running = True
        self.start_time = time.time()
        self.setup_gui()
        self.setup_overclocking()  # Additional setup if needed
        
        # Start periodic updates
        self.update_info()      # Dynamic info (core speeds, available RAM)
        self.update_monitor()   # CPU and RAM graphs
        self.update_processes() # Process list

    def setup_gui(self):
        self.master.title("Vortex")
        self.master.geometry("800x600")
        
        # Create a Notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.master)
        self.tabs = {}
        for tab_name in ['info', 'monitor', 'overclock', 'processes']:
            self.tabs[tab_name] = ttk.Frame(self.notebook)
            self.notebook.add(self.tabs[tab_name], text=tab_name.capitalize())
        self.notebook.pack(expand=True, fill='both')
        
        # Create each tab’s content
        self.create_info_tab()
        self.create_monitor_tab()
        self.create_overclock_tab()
        self.create_processes_tab()

    def create_info_tab(self):
        info = self.system_info
        info_text = (
            "----------------- System Information -----------------\n\n"
            "Processor Information:\n"
            f"Name: {info['cpu']['name']}\n"
            f"Architecture: {info['cpu']['arch']}\n"
            f"Cores (Physical): {info['cpu']['cores']}\n"
            f"Threads (Logical): {info['cpu']['threads']}\n"
            f"Base Frequency: {info['cpu']['freq']} MHz\n\n"
            "Operating System:\n"
            f"OS: {info['system']['os']}\n"
            f"Version: {info['system']['version']}\n\n"
            "Memory Information:\n"
            f"Total RAM: {info['system']['memory']['total']} GB\n"
            f"Available RAM: {info['system']['memory']['available']} GB (initial)\n\n"
            "Motherboard Information:\n"
            f"Model: {info['motherboard']}\n"
            "--------------------------------------------------------"
        )
        self.info_label = tk.Label(self.tabs['info'], text=info_text, justify=tk.LEFT, font=("Helvetica", 10))
        self.info_label.pack(anchor="w", padx=10, pady=10)
        
        # Label for dynamic per-core frequency updates
        self.freq_label = tk.Label(self.tabs['info'], text="Core Speeds: Updating...", justify=tk.LEFT, font=("Helvetica", 10))
        self.freq_label.pack(anchor="w", padx=10, pady=5)
        
        # Label for dynamic available RAM updates
        self.ram_info_label = tk.Label(self.tabs['info'], text="Available RAM: Updating...", justify=tk.LEFT, font=("Helvetica", 10))
        self.ram_info_label.pack(anchor="w", padx=10, pady=5)

    def update_info(self):
        # Update per-core frequencies
        freqs = psutil.cpu_freq(percpu=True)
        if freqs:
            freq_text = "Core Speeds: " + ", ".join([f"Core {i}: {f.current:.1f} MHz" for i, f in enumerate(freqs)])
        else:
            freq_text = "Core Speeds: N/A"
        self.freq_label.config(text=freq_text)
        
        # Update available RAM info
        mem = psutil.virtual_memory()
        ram_text = f"Available RAM: {mem.available // (1024**3)} GB"
        self.ram_info_label.config(text=ram_text)
        
        self.master.after(1000, self.update_info)

    def create_monitor_tab(self):
        monitor_frame = self.tabs['monitor']
        # --- CPU Usage Graph ---
        cpu_frame = ttk.Frame(monitor_frame)
        cpu_frame.pack(side=tk.TOP, fill='both', expand=True, padx=10, pady=5)
        
        self.num_cores = psutil.cpu_count(logical=True)
        self.cpu_fig = Figure(figsize=(4, 2), dpi=100)
        self.cpu_ax = self.cpu_fig.add_subplot(111)
        self.cpu_ax.set_title("CPU Usage per Core")
        self.cpu_ax.set_xlabel("Time (s)")
        self.cpu_ax.set_ylabel("Usage (%)")
        self.cpu_ax.set_ylim(0, 100)
        self.cpu_lines = []
        self.cpu_data = []
        self.cpu_x_data = []
        for i in range(self.num_cores):
            line, = self.cpu_ax.plot([], [], label=f"Core {i}", linewidth=1)
            self.cpu_lines.append(line)
            self.cpu_data.append(deque(maxlen=300))
        self.cpu_ax.legend(fontsize=8)
        self.cpu_canvas = FigureCanvasTkAgg(self.cpu_fig, master=cpu_frame)
        self.cpu_canvas.get_tk_widget().pack(expand=True, fill='both')
        
        # --- Available RAM Graph ---
        ram_frame = ttk.Frame(monitor_frame)
        ram_frame.pack(side=tk.TOP, fill='both', expand=True, padx=10, pady=5)
        
        self.ram_fig = Figure(figsize=(4, 2), dpi=100)
        self.ram_ax = self.ram_fig.add_subplot(111)
        self.ram_ax.set_title("Available RAM (%)")
        self.ram_ax.set_xlabel("Time (s)")
        self.ram_ax.set_ylabel("Available (%)")
        self.ram_ax.set_ylim(0, 100)
        self.ram_line, = self.ram_ax.plot([], [], label="RAM Available", color="green", linewidth=1)
        self.ram_ax.legend(fontsize=8)
        self.ram_canvas = FigureCanvasTkAgg(self.ram_fig, master=ram_frame)
        self.ram_canvas.get_tk_widget().pack(expand=True, fill='both')
        self.ram_data = deque(maxlen=300)
        self.ram_x_data = []

    def update_monitor(self):
        current_time = time.time() - self.start_time
        
        # Update CPU usage graph
        self.cpu_x_data.append(current_time)
        cpu_usage = psutil.cpu_percent(percpu=True)
        for i, usage in enumerate(cpu_usage):
            self.cpu_data[i].append(usage)
            x_vals = list(self.cpu_x_data)[-len(self.cpu_data[i]):]
            self.cpu_lines[i].set_data(x_vals, list(self.cpu_data[i]))
        self.cpu_ax.set_xlim(max(0, current_time - 60), current_time + 1)
        self.cpu_canvas.draw_idle()
        
        # Update RAM usage graph (available memory as percentage)
        mem = psutil.virtual_memory()
        available_percent = mem.available / mem.total * 100
        self.ram_x_data.append(current_time)
        self.ram_data.append(available_percent)
        self.ram_line.set_data(list(self.ram_x_data)[-len(self.ram_data):], list(self.ram_data))
        self.ram_ax.set_xlim(max(0, current_time - 60), current_time + 1)
        self.ram_canvas.draw_idle()
        
        if self.running:
            self.master.after(1000, self.update_monitor)

    def create_overclock_tab(self):
        frame = self.tabs['overclock']
        title = tk.Label(frame, text="CPU Overclocking Controls", font=('Arial', 14))
        title.pack(pady=10)
        warning = tk.Label(frame, text="WARNING: Overclocking can damage hardware!", fg='red')
        warning.pack(pady=5)
        
        self.core_controls = []
        physical_cores = self.system_info['cpu']['cores']
        for core in range(physical_cores):
            cf = ttk.Frame(frame)
            cf.pack(pady=2, padx=10, fill='x')
            label = ttk.Label(cf, text=f"Core {core} Controls:")
            label.pack(side=tk.LEFT)
            # Multiplier slider (example range, adjust as needed)
            mult_scale = ttk.Scale(cf, from_=20, to=60, orient='horizontal',
                                   command=lambda v, c=core: self.update_multiplier(c, v))
            mult_scale.set(30)
            mult_scale.pack(side=tk.LEFT, padx=5, fill='x', expand=True)
            # Voltage slider (dummy control)
            volt_scale = ttk.Scale(cf, from_=0.8, to=1.5, orient='horizontal',
                                   command=lambda v, c=core: self.update_voltage(c, v))
            volt_scale.set(1.0)
            volt_scale.pack(side=tk.LEFT, padx=5, fill='x', expand=True)
            self.core_controls.append((mult_scale, volt_scale))
        self.oc_status = tk.Label(frame, text="Ready", font=("Arial", 10))
        self.oc_status.pack(pady=10)
    
    def update_multiplier(self, core, value):
        try:
            if oc_lib:
                oc_lib.set_cpu_multiplier(core, int(float(value)))
                self.oc_status.config(text=f"Core {core} multiplier set to {int(float(value))}", fg='black')
            else:
                self.oc_status.config(text="Overclock library not available", fg='red')
        except Exception as e:
            self.oc_status.config(text=f"Error: {str(e)}", fg='red')
    
    def update_voltage(self, core, value):
        # Voltage control placeholder (requires hardware-specific implementation)
        self.oc_status.config(text=f"Core {core} voltage adjustment: {float(value):.2f}V", fg='black')
    
    def create_processes_tab(self):
        frame = self.tabs['processes']
        title = tk.Label(frame, text="Process Manager", font=('Arial', 14))
        title.pack(pady=10)
        
        columns = ("PID", "Name", "CPU (%)", "Memory (%)", "Threads")
        self.tree = ttk.Treeview(frame, columns=columns, show='headings')
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor='center')
        self.tree.pack(expand=True, fill='both', padx=10, pady=5)
    
    def update_processes(self):
        # Clear current tree items
        for item in self.tree.get_children():
            self.tree.delete(item)
        # Add updated process information
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'num_threads']):
            try:
                self.tree.insert("", "end", values=(
                    proc.info['pid'],
                    proc.info['name'],
                    proc.info['cpu_percent'],
                    f"{proc.info['memory_percent']:.1f}",
                    proc.info['num_threads']
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.master.after(3000, self.update_processes)
    
    def setup_overclocking(self):
        # Additional overclocking initialization if necessary.
        pass
    
    def safe_exit(self):
        self.running = False
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = OverclockingGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.safe_exit)
    root.mainloop()
