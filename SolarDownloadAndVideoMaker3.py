import cv2
import os
import re
import requests
from datetime import datetime
from PIL import Image
from io import BytesIO
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import threading

# Dictionary to map source names to URLs
SOURCE_URLS = {
    'SDO/HMI Continuum': 'https://soho.nascom.nasa.gov/data/realtime/hmi_igr/1024/latest.jpg',
    'SDO/HMI Magnetogram Image': 'https://soho.nascom.nasa.gov/data/realtime/hmi_mag/1024/latest.jpg',
    'EIT 171': 'https://soho.nascom.nasa.gov/data/realtime/eit_171/1024/latest.jpg',
    'EIT 195': 'https://soho.nascom.nasa.gov/data/realtime/eit_195/1024/latest.jpg',
    'EIT 284': 'https://soho.nascom.nasa.gov/data/realtime/eit_284/1024/latest.jpg',
    'EIT 304': 'https://soho.nascom.nasa.gov/data/realtime/eit_304/1024/latest.jpg',
    'SDO/AIA 193': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0193.jpg',
    'SDO/AIA 304': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0304.jpg',
    'SDO/AIA 171': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0171.jpg',
    'SDO/AIA 211': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0211.jpg',
    'SDO/AIA 131': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0131.jpg',
    'SDO/AIA 335': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0335.jpg',
    'SDO/AIA 094': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0094.jpg',
    'SDO/AIA 1600': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_1600.jpg',
    'SDO/AIA 1700': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_1700.jpg',
    'SDO Composite 211-193-171': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_211193171.jpg',
    'SDO Composite 304-211-171': 'https://sdo.gsfc.nasa.gov/assets/img/latest/f_304_211_171_1024.jpg',
    'SDO Composite 094-335-193': 'https://sdo.gsfc.nasa.gov/assets/img/latest/f_094_335_193_1024.jpg',
    'SDO HMI Magnetogram 171': 'https://sdo.gsfc.nasa.gov/assets/img/latest/f_HMImag_171_1024.jpg',
    'SDO HMI Continuum Blue': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMIBC.jpg',
    'SDO HMI Continuum Intensitygram': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMIIC.jpg',
    'SDO HMI Continuum Full Disk': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMIIF.jpg',
    'SDO HMI Intensitygram': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMII.jpg',
    'SDO HMI Dopplergram': 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMID.jpg'
}

# Global variable to control the download loop
running = True
input_dir = ""  # Initialize input_dir
fps = 24  # Default FPS
lock = threading.Lock()

def natural_sort_key(s):
    # Extracts the numerical part (image number) after the last underscore in the filename for correct sorting
    match = re.search(r'_(\d+)\.jpg$', s)
    return int(match.group(1)) if match else 0

def create_video_from_jpegs(input_dir, output_file, fps=24, start_number=1):
    print("Creating video...")
    image_files = [f for f in os.listdir(input_dir) if f.endswith('.jpg') or f.endswith('.jpeg')]
    if not image_files:
        print("No JPEG files found in the directory")
        return

    image_files.sort(key=natural_sort_key)

    # Ensure we start from the lowest image number
    min_number = min(int(re.findall(r'\d+', f)[-1]) for f in image_files)
    image_files = [f for f in image_files if int(re.findall(r'\d+', f)[-1]) >= min_number]

    if not image_files:
        print("No images found after the starting number.")
        return

    # Read the first image to get dimensions
    try:
        first_image = cv2.imread(os.path.join(input_dir, image_files[0]))
        height, width, _ = first_image.shape
    except Exception as e:
        print(f"Error reading image dimensions: {e}")
        return

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

    for image_file in image_files:
        image_path = os.path.join(input_dir, image_file)
        frame = cv2.imread(image_path)
        if frame is not None:
            out.write(frame)
            print(f"Added {image_file} to video")
        else:
            print(f"Error reading image {image_file}")

    out.release()
    cv2.destroyAllWindows()
    print("Video creation complete.")

def start_download():
    global running
    with lock:
        running = True
    
    try:
        num_images = int(entry_num_images.get())
        time_interval = int(entry_time_interval.get()) * 60  # Convert minutes to seconds
        target_directory = entry_directory.get()
        selected_source = url_combobox.get()
        image_source_url = SOURCE_URLS.get(selected_source, None)
        start_number = int(entry_start_number.get())

        # Validate inputs
        if num_images <= 0 or time_interval <= 0 or start_number < 1:
            messagebox.showerror("Invalid Input", "Please enter positive values for images, time interval, and start number.")
            return
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
        if not image_source_url:
            messagebox.showerror("Invalid Selection", "Please select a valid image source.")
            return

        image_counter = start_number

        while True:
            with lock:
                if not running:
                    break

            # Get the current date and format it as "ddmonyy"
            current_date = datetime.now()
            formatted_date = current_date.strftime('%d%b%y').lower()

            try:
                response = requests.get(image_source_url, timeout=10)
                response.raise_for_status()  # Raise an exception for HTTP errors
            except requests.exceptions.RequestException as e:
                print(f"Error fetching image: {e}")
                messagebox.showerror("Download Error", f"Failed to download image: {e}")
                break

            # Open the image using PIL
            image = Image.open(BytesIO(response.content))

            # Construct the filename with an incrementing counter
            filename = '{}_sun_{}.jpg'.format(formatted_date, image_counter)
            image_counter += 1

            # Save the image to the specified folder
            image.save(os.path.join(target_directory, filename))
            print(f"Image saved as {filename}")
            status_label.config(text=f"Saved {filename}...")

            if image_counter > start_number + num_images - 1:
                break

            # Countdown timer
            for i in range(time_interval, 0, -1):
                with lock:
                    if not running:
                        break
                status_label.config(text=f"Next image in {i} seconds...")
                time.sleep(1)

        status_label.config(text="Download Complete!")
        if running:
            messagebox.showinfo("Download Complete", "All images have been successfully downloaded.")
    
    except ValueError:
        messagebox.showerror("Invalid Input", "Please enter valid numbers for images, time interval, and start number.")
    finally:
        with lock:
            running = False

def stop_download():
    global running
    with lock:
        running = False
    status_label.config(text="Download Stopped.")

def browse_directory():
    directory = filedialog.askdirectory()
    global input_dir
    if directory:
        entry_directory.delete(0, tk.END)
        entry_directory.insert(0, directory)
        input_dir = directory

def make_mp4():
    global input_dir, fps
    if input_dir:
        output_file = os.path.join(input_dir, "output.mp4")
        create_video_from_jpegs(input_dir, output_file, fps=fps, start_number=1)
        messagebox.showinfo("Video Creation Complete", f"MP4 video created successfully: {output_file}")
    else:
        messagebox.showerror("Directory Error", "Please specify a directory containing images.")

def update_fps():
    global fps
    try:
        fps = int(entry_fps.get())
        if fps <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Invalid Input", "FPS must be a positive integer.")
        
def on_closing():
    stop_download()
    root.destroy()

# GUI Setup
root = tk.Tk()
root.title("Solar Image Downloader & MP4 Creator -- TVP")
root.geometry("415x400")

# Number of images to download
tk.Label(root, text="Number of Images:").pack()
entry_num_images = tk.Entry(root)
entry_num_images.pack()

# Time interval between images (in minutes)
tk.Label(root, text="Time Interval (minutes):").pack()
entry_time_interval = tk.Entry(root)
entry_time_interval.pack()

ttk.Label(root, text="Start Image Number:").pack()
entry_start_number = ttk.Entry(root)
entry_start_number.pack()

# Target directory for saving images
tk.Label(root, text="Save Images To:").pack()
entry_directory = tk.Entry(root, width=50)
entry_directory.pack()
browse_button = tk.Button(root, text="Browse", command=browse_directory)
browse_button.pack()

# Status label
status_label = tk.Label(root, text="Waiting to start...")
status_label.pack()

# Source selection
tk.Label(root, text="Select Image Source:").pack()
url_combobox = ttk.Combobox(root, values=list(SOURCE_URLS.keys()), width=50)
url_combobox.pack()
url_combobox.set("SDO/HMI Continuum")  # Default selection

# Start/Stop buttons
start_button = tk.Button(root, text="Start Download", command=lambda: threading.Thread(target=start_download).start())
start_button.pack()

stop_button = tk.Button(root, text="Stop Download", command=stop_download)
stop_button.pack()

# FPS input for video
tk.Label(root, text="Frames per Second (FPS) for Video:").pack()
entry_fps = tk.Entry(root)
entry_fps.insert(0, str(fps))  # Default FPS
entry_fps.pack()

update_fps_button = tk.Button(root, text="Update FPS", command=update_fps)
update_fps_button.pack()

# Create video button
video_button = tk.Button(root, text="Create MP4 from Images", command=make_mp4)
video_button.pack()

# Set the function to call when the window is closed
root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()
