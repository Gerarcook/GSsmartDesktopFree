import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Test")
app.geometry("400x300")
label = ctk.CTkLabel(app, text="Hello World")
label.pack(pady=20)
app.mainloop()