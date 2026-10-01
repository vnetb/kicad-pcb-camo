"""
PCB Camouflage ActionPlugin for KiCad Pcbnew.
Integrates into the toolbar and Tools menu.
"""

import os
import pcbnew
import wx
from .dialog import PCBCamouflageDialog


class PCBCamouflagePlugin(pcbnew.ActionPlugin):
    """ActionPlugin to launch the PCB Camouflage Dialog."""

    def defaults(self):
        self.name = "PCB Camouflage (Dazzle & Swirl)"
        self.category = "Silkscreen Art & Security"
        self.description = (
            "Generate automotive prototype-style dazzle / swirl camouflage on silkscreen "
            "with automatic pad avoidance, and safely stash/restore silkscreen items to User layers."
        )
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "icon.png")
        self.dlg = None

    def Run(self):
        # Singleton dialog handling
        if self.dlg:
            try:
                self.dlg.Iconize(False)
                self.dlg.Raise()
                self.dlg.Show()
                self.dlg.RequestUserAttention()
                return
            except Exception:
                self.dlg = None

        parent = None
        self.dlg = PCBCamouflageDialog(parent)
        self.dlg.Show()
