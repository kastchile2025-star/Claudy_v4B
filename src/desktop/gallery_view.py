import os
import time
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageOps, ImageFilter

# ----------------- Styles & Colors -----------------
BG_DARK = "#151821"
BG_CARD = "#1c1f2b"
TEXT_PRIMARY = "#ece9f5"
TEXT_MUTED = "#9fb2ff"
ACCENT_PRIMARY = "#c4b5fd"
ACCENT_DARK = "#1f4e78"
BUTTON_HOVER = "#2e75b6"

class ScrollableFrame(tk.Frame):
    """A scrollable Tkinter frame container using canvas and Scrollbar."""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=BG_DARK, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=BG_DARK)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Handle resizing of container to expand the internal frame width
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _on_canvas_configure(self, event):
        # Update the width of the scrollable frame to match the canvas width
        self.canvas.itemconfig(self.canvas_window, width=event.width)


class ImageEditorWindow(tk.Toplevel):
    """A full-featured visual image editor window using PIL."""
    def __init__(self, parent, image_path, on_save_callback=None):
        super().__init__(parent)
        self.title(f"Editor de Imagen - {os.path.basename(image_path)}")
        self.geometry("1000x750")
        self.configure(bg=BG_DARK)
        self.transient(parent)
        self.grab_set()

        self.image_path = image_path
        self.on_save_callback = on_save_callback
        
        # Editor State
        try:
            self.original_image = Image.open(image_path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la imagen:\n{e}")
            self.destroy()
            return
            
        self.current_image = self.original_image.copy()
        
        self.rotation = 0
        self.flip_h = False
        self.flip_v = False
        self.filter_mode = None # grayscale, sepia, invert, blur, None
        
        # Interactive Crop State
        self.crop_active = False
        self.crop_rect_id = None
        self.crop_start_x = None
        self.crop_start_y = None
        self.crop_end_x = None
        self.crop_end_y = None
        
        self.build_ui()
        self.bind_events()
        
        # Force initial display layout calculations
        self.update_idletasks()
        self.display_image()

    def build_ui(self):
        # Main vertical structure
        # Top Header
        header = tk.Frame(self, bg=BG_DARK, height=50)
        header.pack(side="top", fill="x", padx=15, pady=10)
        
        title_lbl = tk.Label(header, text="🎨 Editor de Imagen Claudy", font=("Bahnschrift", 14, "bold"), fg=TEXT_PRIMARY, bg=BG_DARK)
        title_lbl.pack(side="left")
        
        path_lbl = tk.Label(header, text=self.image_path, font=("Consolas", 9), fg=TEXT_MUTED, bg=BG_DARK)
        path_lbl.pack(side="right")
        
        # Main body (left canvas, right sidebar controls)
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(side="top", fill="both", expand=True)
        
        # Left Image Canvas Area
        canvas_container = tk.Frame(body, bg=BG_DARK, bd=1, relief="solid", highlightbackground=ACCENT_PRIMARY)
        canvas_container.pack(side="left", fill="both", expand=True, padx=(15, 10), pady=10)
        
        self.canvas = tk.Canvas(canvas_container, bg="#10121a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Right Sidebar Controls
        sidebar = tk.Frame(body, bg=BG_CARD, width=280)
        sidebar.pack(side="right", fill="y", padx=(10, 15), pady=10)
        sidebar.pack_propagate(False)
        
        # Scrollable sidebar components
        ctrl_canvas = tk.Canvas(sidebar, bg=BG_CARD, highlightthickness=0)
        ctrl_scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=ctrl_canvas.yview)
        self.ctrl_frame = tk.Frame(ctrl_canvas, bg=BG_CARD)
        
        self.ctrl_frame.bind(
            "<Configure>",
            lambda e: ctrl_canvas.configure(scrollregion=ctrl_canvas.bbox("all"))
        )
        ctrl_canvas.create_window((0, 0), window=self.ctrl_frame, anchor="nw", width=260)
        ctrl_canvas.configure(yscrollcommand=ctrl_scrollbar.set)
        
        ctrl_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        ctrl_scrollbar.pack(side="right", fill="y")

        # --- Sidebar Sections ---
        # 1. Sliders Block
        section_adj = tk.LabelFrame(self.ctrl_frame, text=" Ajustes de Luz y Color ", font=("Bahnschrift", 10, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD, bd=1, relief="groove")
        section_adj.pack(fill="x", padx=5, pady=10)
        
        # Brightness
        tk.Label(section_adj, text="Brillo", font=("Bahnschrift", 9), fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=10, pady=(5, 0))
        self.bright_scale = tk.Scale(section_adj, from_=0.0, to=2.0, resolution=0.05, orient="horizontal", bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=ACCENT_PRIMARY, highlightthickness=0, command=lambda v: self.apply_enhancements())
        self.bright_scale.set(1.0)
        self.bright_scale.pack(fill="x", padx=10, pady=(0, 5))
        
        # Contrast
        tk.Label(section_adj, text="Contraste", font=("Bahnschrift", 9), fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=10, pady=(5, 0))
        self.contrast_scale = tk.Scale(section_adj, from_=0.0, to=2.0, resolution=0.05, orient="horizontal", bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=ACCENT_PRIMARY, highlightthickness=0, command=lambda v: self.apply_enhancements())
        self.contrast_scale.set(1.0)
        self.contrast_scale.pack(fill="x", padx=10, pady=(0, 5))
        
        # Saturation (Color)
        tk.Label(section_adj, text="Saturación", font=("Bahnschrift", 9), fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=10, pady=(5, 0))
        self.color_scale = tk.Scale(section_adj, from_=0.0, to=2.0, resolution=0.05, orient="horizontal", bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=ACCENT_PRIMARY, highlightthickness=0, command=lambda v: self.apply_enhancements())
        self.color_scale.set(1.0)
        self.color_scale.pack(fill="x", padx=10, pady=(0, 5))

        # Sharpness
        tk.Label(section_adj, text="Nitidez", font=("Bahnschrift", 9), fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=10, pady=(5, 0))
        self.sharp_scale = tk.Scale(section_adj, from_=0.0, to=2.0, resolution=0.05, orient="horizontal", bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=ACCENT_PRIMARY, highlightthickness=0, command=lambda v: self.apply_enhancements())
        self.sharp_scale.set(1.0)
        self.sharp_scale.pack(fill="x", padx=10, pady=(0, 5))

        # 2. Transform Actions
        section_trans = tk.LabelFrame(self.ctrl_frame, text=" Transformar ", font=("Bahnschrift", 10, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD, bd=1, relief="groove")
        section_trans.pack(fill="x", padx=5, pady=10)
        
        btn_grid = tk.Frame(section_trans, bg=BG_CARD)
        btn_grid.pack(fill="x", padx=10, pady=5)
        
        self.btn_rot_cw = tk.Button(btn_grid, text="🔄 Rotar 90°", font=("Bahnschrift", 9), bg=ACCENT_DARK, fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY, relief="flat", command=lambda: self.rotate_image(90))
        self.btn_rot_cw.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        
        self.btn_rot_ccw = tk.Button(btn_grid, text="🔄 Rotar -90°", font=("Bahnschrift", 9), bg=ACCENT_DARK, fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY, relief="flat", command=lambda: self.rotate_image(-90))
        self.btn_rot_ccw.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        
        self.btn_flip_h = tk.Button(btn_grid, text="↔️ Espejo H", font=("Bahnschrift", 9), bg=ACCENT_DARK, fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY, relief="flat", command=self.toggle_flip_h)
        self.btn_flip_h.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        
        self.btn_flip_v = tk.Button(btn_grid, text="↕️ Espejo V", font=("Bahnschrift", 9), bg=ACCENT_DARK, fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY, relief="flat", command=self.toggle_flip_v)
        self.btn_flip_v.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        # 3. Filters
        section_filt = tk.LabelFrame(self.ctrl_frame, text=" Filtros de Efecto ", font=("Bahnschrift", 10, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD, bd=1, relief="groove")
        section_filt.pack(fill="x", padx=5, pady=10)
        
        filters = [("Ninguno", None), ("Escala de Grises", "grayscale"), ("Sepia", "sepia"), ("Invertido", "invert"), ("Desenfocar", "blur")]
        self.filter_var = tk.StringVar(value="None")
        
        for text, mode in filters:
            r = tk.Radiobutton(section_filt, text=text, variable=self.filter_var, value=str(mode), font=("Bahnschrift", 9), bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=BG_CARD, activeforeground=TEXT_PRIMARY, selectcolor=BG_DARK, command=lambda m=mode: self.set_filter(m))
            r.pack(anchor="w", padx=15, pady=2)

        # 4. Interactive Crop Block
        section_crop = tk.LabelFrame(self.ctrl_frame, text=" Recortar Imagen ", font=("Bahnschrift", 10, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD, bd=1, relief="groove")
        section_crop.pack(fill="x", padx=5, pady=10)
        
        self.crop_btn = tk.Button(section_crop, text="Iniciar Recorte", font=("Bahnschrift", 9, "bold"), bg=ACCENT_DARK, fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY, relief="flat", command=self.toggle_crop_mode)
        self.crop_btn.pack(fill="x", padx=15, pady=5)
        
        self.apply_crop_btn = tk.Button(section_crop, text="Aplicar Selección", font=("Bahnschrift", 9, "bold"), bg="green", fg=TEXT_PRIMARY, activebackground="#00aa00", activeforeground=TEXT_PRIMARY, relief="flat", state="disabled", command=self.apply_crop)
        self.apply_crop_btn.pack(fill="x", padx=15, pady=5)
        
        # 5. Saving and Closing
        section_save = tk.Frame(self.ctrl_frame, bg=BG_CARD)
        section_save.pack(fill="x", padx=5, pady=15)
        
        self.save_btn = tk.Button(section_save, text="💾 Guardar Cambios", font=("Bahnschrift", 10, "bold"), bg="#1A6F2A", fg=TEXT_PRIMARY, activebackground="#1E8F35", activeforeground=TEXT_PRIMARY, relief="flat", command=self.save_changes)
        self.save_btn.pack(fill="x", pady=4)
        
        self.save_as_btn = tk.Button(section_save, text="📂 Guardar Como...", font=("Bahnschrift", 9), bg=ACCENT_DARK, fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY, relief="flat", command=self.save_as_new)
        self.save_as_btn.pack(fill="x", pady=4)
        
        self.revert_btn = tk.Button(section_save, text="🔄 Deshacer Todo", font=("Bahnschrift", 9), bg="#6F1A1A", fg=TEXT_PRIMARY, activebackground="#8F1A1A", activeforeground=TEXT_PRIMARY, relief="flat", command=self.revert_changes)
        self.revert_btn.pack(fill="x", pady=4)

    def bind_events(self):
        # Resize dynamic adjustments
        self.canvas.bind("<Configure>", lambda e: self.display_image())
        
        # Mouse events for custom cropping rectangle
        self.canvas.bind("<ButtonPress-1>", self.on_crop_press)
        self.canvas.bind("<B1-Motion>", self.on_crop_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_crop_release)

    def reset_sliders(self):
        self.bright_scale.set(1.0)
        self.contrast_scale.set(1.0)
        self.color_scale.set(1.0)
        self.sharp_scale.set(1.0)

    def display_image(self):
        if self.current_image is None:
            return
            
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        
        if canvas_w < 10: canvas_w = 600
        if canvas_h < 10: canvas_h = 500
        
        img_w, img_h = self.current_image.size
        
        # Preserve Aspect Ratio
        scale = min(canvas_w / img_w, canvas_h / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        
        if new_w < 1 or new_h < 1:
            return
            
        resized_img = self.current_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_img)
        
        self.canvas.delete("all")
        # Center image coordinates
        self.img_x = (canvas_w - new_w) // 2
        self.img_y = (canvas_h - new_h) // 2
        self.canvas.create_image(self.img_x, self.img_y, anchor="nw", image=self.tk_image)
        
        self.disp_w = new_w
        self.disp_h = new_h
        self.scale_factor = img_w / new_w

    def rotate_image(self, angle):
        self.rotation = (self.rotation + angle) % 360
        self.apply_enhancements()

    def toggle_flip_h(self):
        self.flip_h = not self.flip_h
        self.apply_enhancements()

    def toggle_flip_v(self):
        self.flip_v = not self.flip_v
        self.apply_enhancements()

    def set_filter(self, mode):
        self.filter_mode = mode if mode != "None" else None
        self.apply_enhancements()

    def apply_enhancements(self):
        if self.original_image is None:
            return
            
        # Start base transformations from original
        img = self.original_image.copy()
        
        # Apply crop step (since crop modifies original_image directly, this is handled)
        
        # Apply Rotation / Flip
        if self.rotation != 0:
            img = img.rotate(self.rotation, expand=True)
        if self.flip_h:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if self.flip_v:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            
        # Apply Filter Modes
        if self.filter_mode == "grayscale":
            img = ImageOps.grayscale(img).convert("RGB")
        elif self.filter_mode == "sepia":
            gray = ImageOps.grayscale(img)
            sepia_data = []
            for pixel in gray.getdata():
                r = int(pixel * 0.9 + 20)
                g = int(pixel * 0.8 + 10)
                b = int(pixel * 0.7)
                sepia_data.append((min(r, 255), min(g, 255), min(b, 255)))
            img = Image.new("RGB", gray.size)
            img.putdata(sepia_data)
        elif self.filter_mode == "invert":
            if img.mode == "RGBA":
                r, g, b, a = img.split()
                rgb = Image.merge("RGB", (r, g, b))
                inv = ImageOps.invert(rgb)
                r2, g2, b2 = inv.split()
                img = Image.merge("RGBA", (r2, g2, b2, a))
            else:
                img = ImageOps.invert(img)
        elif self.filter_mode == "blur":
            img = img.filter(ImageFilter.GaussianBlur(3))
            
        # Apply Enhancer Sliders
        # 1. Brightness
        b_val = self.bright_scale.get()
        if b_val != 1.0:
            img = ImageEnhance.Brightness(img).enhance(b_val)
            
        # 2. Contrast
        c_val = self.contrast_scale.get()
        if c_val != 1.0:
            img = ImageEnhance.Contrast(img).enhance(c_val)
            
        # 3. Saturation (Color)
        s_val = self.color_scale.get()
        if s_val != 1.0 and img.mode in ("RGB", "RGBA"):
            img = ImageEnhance.Color(img).enhance(s_val)

        # 4. Sharpness
        sh_val = self.sharp_scale.get()
        if sh_val != 1.0:
            img = ImageEnhance.Sharpness(img).enhance(sh_val)
            
        self.current_image = img
        self.display_image()

    # --- Interactive Crop Logic ---
    def toggle_crop_mode(self):
        self.crop_active = not self.crop_active
        if self.crop_active:
            self.crop_btn.configure(text="Recortando...", bg="#8f1a1a")
            self.canvas.configure(cursor="cross")
            messagebox.showinfo("Modo Recorte", "Arrastra con el mouse para seleccionar el área y luego presiona 'Aplicar Selección'.")
        else:
            self.crop_btn.configure(text="Iniciar Recorte", bg=ACCENT_DARK)
            self.canvas.configure(cursor="")
            if self.crop_rect_id:
                self.canvas.delete(self.crop_rect_id)
                self.crop_rect_id = None
            self.apply_crop_btn.configure(state="disabled")

    def on_crop_press(self, event):
        if not self.crop_active:
            return
        self.crop_start_x = event.x
        self.crop_start_y = event.y
        if self.crop_rect_id:
            self.canvas.delete(self.crop_rect_id)
        # Lavender border dashed rectangle
        self.crop_rect_id = self.canvas.create_rectangle(
            self.crop_start_x, self.crop_start_y, event.x, event.y,
            outline=ACCENT_PRIMARY, width=2, dash=(4, 4)
        )

    def on_crop_drag(self, event):
        if not self.crop_active or self.crop_start_x is None:
            return
        self.canvas.coords(
            self.crop_rect_id,
            self.crop_start_x, self.crop_start_y, event.x, event.y
        )

    def on_crop_release(self, event):
        if not self.crop_active or self.crop_start_x is None:
            return
        self.crop_end_x = event.x
        self.crop_end_y = event.y
        self.apply_crop_btn.configure(state="normal")

    def apply_crop(self):
        if self.crop_start_x is None or self.crop_end_x is None:
            return
            
        # Bounds inside display image
        x1 = min(self.crop_start_x, self.crop_end_x) - self.img_x
        y1 = min(self.crop_start_y, self.crop_end_y) - self.img_y
        x2 = max(self.crop_start_x, self.crop_end_x) - self.img_x
        y2 = max(self.crop_start_y, self.crop_end_y) - self.img_y
        
        # Clamp to canvas display image box
        x1 = max(0, min(self.disp_w, x1))
        y1 = max(0, min(self.disp_h, y1))
        x2 = max(0, min(self.disp_w, x2))
        y2 = max(0, min(self.disp_h, y2))
        
        # Scale coordinates back to current_image coordinates
        orig_x1 = int(x1 * self.scale_factor)
        orig_y1 = int(y1 * self.scale_factor)
        orig_x2 = int(x2 * self.scale_factor)
        orig_y2 = int(y2 * self.scale_factor)
        
        if orig_x2 - orig_x1 < 4 or orig_y2 - orig_y1 < 4:
            messagebox.showwarning("Área pequeña", "Selecciona una zona de recorte más grande.")
            return
            
        # Crop & update original_image context
        cropped = self.current_image.crop((orig_x1, orig_y1, orig_x2, orig_y2))
        self.original_image = cropped
        self.current_image = cropped
        
        # Reset relative state changes so they aren't reapplied on top of new dimensions
        self.rotation = 0
        self.flip_h = False
        self.flip_v = False
        self.filter_mode = None
        self.filter_var.set("None")
        self.reset_sliders()
        
        # Reset cropping UI indicator
        self.crop_active = False
        self.crop_btn.configure(text="Iniciar Recorte", bg=ACCENT_DARK)
        self.canvas.configure(cursor="")
        if self.crop_rect_id:
            self.canvas.delete(self.crop_rect_id)
            self.crop_rect_id = None
        self.apply_crop_btn.configure(state="disabled")
        
        self.display_image()
        messagebox.showinfo("Recorte", "Recorte aplicado con éxito.")

    # --- Save Ops ---
    def save_changes(self):
        try:
            # Create a backup file copy in ~/.claudy/file_backups/
            backup_dir = os.path.join(os.path.expanduser("~"), ".claudy", "file_backups")
            os.makedirs(backup_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{ts}__{os.path.basename(self.image_path)}.bak")
            shutil.copy2(self.image_path, backup_path)
            
            # Save new edit image
            self.current_image.save(self.image_path)
            
            if self.on_save_callback:
                self.on_save_callback()
                
            messagebox.showinfo("Guardado", f"Cambios guardados en la imagen original.\nRespaldo creado en:\n{backup_path}")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron guardar los cambios:\n{e}")

    def save_as_new(self):
        ext = os.path.splitext(self.image_path)[1].lower()
        filetypes = [("PNG files", "*.png"), ("JPEG files", "*.jpg;*.jpeg"), ("All files", "*.*")]
        
        dest_path = filedialog.asksaveasfilename(
            title="Guardar Como",
            initialfile=f"editada_{os.path.basename(self.image_path)}",
            filetypes=filetypes,
            defaultextension=ext
        )
        
        if not dest_path:
            return
            
        try:
            self.current_image.save(dest_path)
            if self.on_save_callback:
                self.on_save_callback()
            messagebox.showinfo("Guardado", f"Copia guardada con éxito en:\n{dest_path}")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la imagen:\n{e}")

    def revert_changes(self):
        if messagebox.askyesno("Confirmar", "¿Seguro que deseas deshacer todos los cambios realizados en esta sesión?"):
            self.current_image = self.original_image.copy()
            self.rotation = 0
            self.flip_h = False
            self.flip_v = False
            self.filter_mode = None
            self.filter_var.set("None")
            self.reset_sliders()
            self.display_image()


class ImageGalleryWindow(tk.Toplevel):
    """Main image gallery container with a grid layout and folder refresh logic."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Galería de Imágenes Claudy")
        self.geometry("900x650")
        self.configure(bg=BG_DARK)
        self.transient(parent)
        
        # Default directory
        self.current_dir = os.path.join(os.path.expanduser("~"), ".claudy", "generated")
        os.makedirs(self.current_dir, exist_ok=True)
        
        self.tk_thumbs = [] # Keeps references to PIL images to avoid garbage collection
        
        self.build_ui()
        self.load_images()

    def build_ui(self):
        # 1. Top Panel Toolbar
        toolbar = tk.Frame(self, bg=BG_DARK, height=60)
        toolbar.pack(side="top", fill="x", padx=20, pady=10)
        
        title_lbl = tk.Label(toolbar, text="🖼️ Galería de Imágenes", font=("Bahnschrift", 16, "bold"), fg=TEXT_PRIMARY, bg=BG_DARK)
        title_lbl.pack(side="left")
        
        self.dir_lbl = tk.Label(toolbar, text=self.current_dir, font=("Consolas", 9), fg=TEXT_MUTED, bg=BG_DARK)
        self.dir_lbl.pack(side="left", padx=20)
        
        # Buttons on right
        btn_container = tk.Frame(toolbar, bg=BG_DARK)
        btn_container.pack(side="right")
        
        change_dir_btn = tk.Button(btn_container, text="📂 Cambiar Carpeta", font=("Bahnschrift", 9), bg=ACCENT_DARK, fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY, relief="flat", padx=10, command=self.change_directory)
        change_dir_btn.pack(side="left", padx=4)
        
        refresh_btn = tk.Button(btn_container, text="🔄 Refrescar", font=("Bahnschrift", 9), bg=ACCENT_DARK, fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY, relief="flat", padx=10, command=self.load_images)
        refresh_btn.pack(side="left", padx=4)

        # 2. Main Scrollable Image Grid
        self.grid_container = ScrollableFrame(self, bg=BG_DARK)
        self.grid_container.pack(side="top", fill="both", expand=True, padx=20, pady=10)
        
        # We listen to windows resize events to layout cards adaptively
        self.grid_container.scrollable_frame.bind("<Configure>", lambda e: self.relayout_grid())

    def change_directory(self):
        new_dir = filedialog.askdirectory(initialdir=self.current_dir, title="Selecciona la carpeta de imágenes")
        if new_dir:
            self.current_dir = new_dir
            self.dir_lbl.configure(text=new_dir)
            self.load_images()

    def load_images(self):
        # Clean existing grid
        for child in self.grid_container.scrollable_frame.winfo_children():
            child.destroy()
            
        self.tk_thumbs.clear()
        self.image_paths = []
        
        # Gather images
        valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".gif")
        try:
            for f in os.listdir(self.current_dir):
                full_path = os.path.join(self.current_dir, f)
                if os.path.isfile(full_path) and f.lower().endswith(valid_extensions):
                    self.image_paths.append(full_path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el directorio:\n{e}")
            return
            
        # Sort by modification time (newest first)
        self.image_paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        
        if not self.image_paths:
            no_img_lbl = tk.Label(self.grid_container.scrollable_frame, text="No se encontraron imágenes en esta carpeta.\n¡Pídele a Claudy que te dibuje algo!", font=("Bahnschrift", 12), fg=TEXT_MUTED, bg=BG_DARK)
            no_img_lbl.pack(expand=True, pady=100)
            return

        # Render Image Cards
        self.cards = []
        for idx, img_path in enumerate(self.image_paths):
            card = tk.Frame(self.grid_container.scrollable_frame, bg=BG_CARD, bd=1, relief="solid", highlightthickness=0, highlightbackground="#252b3c")
            
            # Label/Image Box
            img_box = tk.Label(card, bg=BG_CARD, cursor="hand2")
            img_box.pack(side="top", padx=10, pady=(10, 5))
            
            # Load and create thumbnail
            try:
                img = Image.open(img_path)
                img.thumbnail((140, 140))
                tk_thumb = ImageTk.PhotoImage(img)
                self.tk_thumbs.append(tk_thumb) # Avoid garbage collection
                img_box.configure(image=tk_thumb)
            except Exception:
                # Placeholder for corrupt files
                placeholder = Image.new("RGB", (140, 140), "#333333")
                tk_thumb = ImageTk.PhotoImage(placeholder)
                self.tk_thumbs.append(tk_thumb)
                img_box.configure(image=tk_thumb)
                
            # Text information
            fname = os.path.basename(img_path)
            if len(fname) > 20:
                fname = fname[:18] + "..."
            
            lbl_name = tk.Label(card, text=fname, font=("Bahnschrift", 9), fg=TEXT_PRIMARY, bg=BG_CARD)
            lbl_name.pack(side="top", pady=2)
            
            mtime = os.path.getmtime(img_path)
            date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
            lbl_date = tk.Label(card, text=date_str, font=("Bahnschrift", 8), fg=TEXT_MUTED, bg=BG_CARD)
            lbl_date.pack(side="top", pady=(0, 10))
            
            # Bindings for editor access
            card.bind("<Double-Button-1>", lambda e, p=img_path: self.open_editor(p))
            img_box.bind("<Double-Button-1>", lambda e, p=img_path: self.open_editor(p))
            
            # Hover highlight animations
            self.bind_hover_effects(card, [lbl_name, lbl_date, img_box])
            
            self.cards.append(card)
            
        self.relayout_grid()

    def bind_hover_effects(self, parent_widget, sub_widgets):
        def on_enter(e):
            parent_widget.configure(bg="#222533", highlightbackground=ACCENT_PRIMARY)
            for w in sub_widgets:
                w.configure(bg="#222533")
                
        def on_leave(e):
            parent_widget.configure(bg=BG_CARD, highlightbackground="#252b3c")
            for w in sub_widgets:
                w.configure(bg=BG_CARD)
                
        parent_widget.bind("<Enter>", on_enter)
        parent_widget.bind("<Leave>", on_leave)
        for w in sub_widgets:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

    def relayout_grid(self):
        if not hasattr(self, 'cards') or not self.cards:
            return
            
        # Calculate column layout adaptively based on width
        container_w = self.grid_container.scrollable_frame.winfo_width()
        card_w = 175 # roughly card size + pad
        
        cols = max(1, container_w // card_w)
        
        for idx, card in enumerate(self.cards):
            card.grid_forget()
            r = idx // cols
            c = idx % cols
            card.grid(row=r, column=c, padx=8, pady=8)
            
        # Distribute remaining columns evenly
        for c in range(cols):
            self.grid_container.scrollable_frame.columnconfigure(c, weight=1)

    def open_editor(self, image_path):
        ImageEditorWindow(self, image_path, on_save_callback=self.load_images)


def open_gallery_window(pet_instance):
    """Entrypoint to instantiate the gallery window from Tkinter thread."""
    try:
        app = ImageGalleryWindow(pet_instance)
        app.mainloop()
    except Exception as e:
        print("[Image Gallery Error]:", e)


def handle_gallery_prompt(pet, prompt):
    lower = prompt.lower().strip()
    
    # Check trigger commands
    if lower in ("/galeria", "/gallery", "/editor", "/imagenes", "/imágenes"):
        import threading
        # Launch gallery from main thread safely
        pet.after(0, lambda: open_gallery_window(pet))
        return True, "🎨 He abierto la Galería de Imágenes y Editor local en una nueva ventana."
        
    return False, ""
