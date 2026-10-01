"""
PCB Camouflage Plugin Package Initialization.
Registers the ActionPlugin into KiCad Pcbnew.
"""

try:
    from .plugin import PCBCamouflagePlugin
    plugin = PCBCamouflagePlugin()
    plugin.register()
    print("[PCBCamouflage] Plugin registered successfully.")
except Exception as e:
    print(f"[PCBCamouflage] Failed to register plugin: {e}")
    import traceback
    traceback.print_exc()
