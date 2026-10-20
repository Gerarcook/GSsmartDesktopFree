import sys
sys.path.insert(0, r"C:\Users\Administrator\Trabajo\GSsmartDesktopFree")
import customtkinter as ctk
import gui_main as g
app = g.App(); app.update_idletasks()
print("App OK", flush=True)
fb = app.footer_bar
for a in ("entry","send_btn","attach_btn","model_pick_btn"):
    print("  footer.%-15s %s" % (a, "OK" if hasattr(fb,a) else "FALTA"), flush=True)
app.pick_model(); app.update_idletasks(); app.update()
print("selector abierto:", app._model_win is not None, flush=True)
app._set_models(["auto/coding:free","hcnsec/Qwen3.8-Flash-Next","gpt-4o"])
app.update()
print("modelos en lista:", len(app.model_list.winfo_children()), flush=True)
app.model_filter.insert(0,"Qwen"); app._refresh_model_list(); app.update()
print("filtro Qwen:", len(app.model_list.winfo_children()), flush=True)
app.destroy()
print("OK", flush=True)
