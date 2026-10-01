"""
Dialog UI for PCB Camouflage Plugin.
Provides two tabs:
1. Camouflage Generator (Test Mule Swirl, Geometric Dazzle, Zebra Waves) with Pad Avoidance
2. Silkscreen Stash & Restore (Move silkscreen items to User.9..User.1 and back)
"""

import wx
import pcbnew
import random
import os
import json
from .camo_generator import CamoGenerator
from .silk_stash import (
    SilkStashManager,
    find_unused_user_layer,
    get_user_layer_candidates,
    get_item_uuid,
    LAYER_F_SILK,
    LAYER_B_SILK,
)


class PCBCamouflageDialog(wx.Dialog):
    """Main dialog window for PCB Camouflage."""

    def __init__(self, parent):
        super().__init__(
            parent,
            title="PCB Camouflage (Test Mule & Dazzle)",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
        )
        self.board = pcbnew.GetBoard()
        self.camo_gen = CamoGenerator(self.board)
        self.stash_mgr = SilkStashManager(self.board)

        self.last_stashed_layer = None
        self.hidden_uuids = []
        self.camo_shape_uuids = []
        self.saved_params = {}

        self.config_file = self.GetConfigFile()
        self.LoadConfig()

        self.InitUI()
        self.Center()
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def GetConfigFile(self):
        """Get path to project-specific camouflage config file."""
        board_path = self.board.GetFileName()
        if not board_path:
            return None
        project_dir = os.path.dirname(board_path)
        project_name = os.path.splitext(os.path.basename(board_path))[0]
        return os.path.join(project_dir, f".{project_name}.pcb_camo.json")

    def LoadConfig(self):
        """Load stored stashed state, hidden item UUIDs, camo shape UUIDs, and parameters."""
        if not self.config_file or not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.hidden_uuids = data.get("hidden_uuids", [])
            self.last_stashed_layer = data.get("last_stashed_layer", None)
            self.camo_shape_uuids = data.get("camo_shape_uuids", [])
            self.saved_params = data.get("params", {})
            self.VerifyAndSanitizeStashState()
        except Exception as e:
            print(f"[PCBCamouflage] Failed to load config: {e}")

    def VerifyAndSanitizeStashState(self):
        """
        Verify whether recorded hidden items are actually hidden on the current board.
        If the user closed KiCad without saving, the board items were restored to visible
        while the external JSON retained stale hidden_uuids.
        Automatically cleans up the stale state so the user can stash cleanly.
        """
        if not self.hidden_uuids:
            return

        hidden_set = set(self.hidden_uuids)
        actually_hidden = 0
        actually_visible = 0

        for fp in self.board.GetFootprints():
            for text_item in (fp.Reference(), fp.Value()):
                if text_item:
                    uid = get_item_uuid(text_item)
                    if uid in hidden_set:
                        if text_item.IsVisible():
                            actually_visible += 1
                        else:
                            actually_hidden += 1

        # If recorded items are actually visible on the board, stale state detected
        if actually_visible > actually_hidden:
            print(
                f"[PCBCamouflage] Stale stash state detected ({actually_visible} items visible vs {actually_hidden} hidden). "
                "Board was likely reloaded without saving. Resetting stashed state."
            )
            self.hidden_uuids = []
            self.last_stashed_layer = None
            self.SaveConfig()

    def SaveConfig(self):
        """Save stashed state, hidden item UUIDs, camo shape UUIDs, and user parameters."""
        if not self.config_file:
            return

        params = dict(self.saved_params)
        if hasattr(self, "choice_side"):
            params["side"] = self.choice_side.GetSelection()
        if hasattr(self, "choice_pattern"):
            params["pattern"] = self.choice_pattern.GetSelection()
        if hasattr(self, "txt_scale_min"):
            params["scale_min"] = self.txt_scale_min.GetValue()
        if hasattr(self, "txt_scale_max"):
            params["scale_max"] = self.txt_scale_max.GetValue()
        if hasattr(self, "txt_line_w_min"):
            params["line_w_min"] = self.txt_line_w_min.GetValue()
        if hasattr(self, "txt_line_w_max"):
            params["line_w_max"] = self.txt_line_w_max.GetValue()
        if hasattr(self, "txt_angle_min"):
            params["angle_min"] = self.txt_angle_min.GetValue()
        if hasattr(self, "txt_angle_max"):
            params["angle_max"] = self.txt_angle_max.GetValue()
        if hasattr(self, "txt_pad_clearance"):
            params["pad_clearance"] = self.txt_pad_clearance.GetValue()
        if hasattr(self, "txt_margin"):
            params["board_margin"] = self.txt_margin.GetValue()
        if hasattr(self, "txt_seed"):
            params["seed"] = self.txt_seed.GetValue()
        if hasattr(self, "chk_clear_existing"):
            params["clear_existing"] = self.chk_clear_existing.IsChecked()

        self.saved_params = params

        data = {
            "hidden_uuids": list(set(self.hidden_uuids)),
            "last_stashed_layer": self.last_stashed_layer,
            "camo_shape_uuids": list(set(self.camo_shape_uuids)),
            "params": params,
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[PCBCamouflage] Failed to save config: {e}")

    def OnClose(self, event):
        self.SaveConfig()
        event.Skip()

    def InitUI(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        notebook = wx.Notebook(self)

        # Tab 1: Camouflage Generation
        tab_camo = wx.Panel(notebook)
        self.BuildCamoTab(tab_camo)
        notebook.AddPage(tab_camo, "Camouflage Generator")

        # Tab 2: Silk Stash & Restore
        tab_stash = wx.Panel(notebook)
        self.BuildStashTab(tab_stash)
        notebook.AddPage(tab_stash, "Silk Stash & Restore")

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 8)

        # Status text at bottom
        self.lbl_status = wx.StaticText(self, label="Ready.")
        main_sizer.Add(self.lbl_status, 0, wx.ALL | wx.EXPAND, 8)

        self.SetSizer(main_sizer)
        self.SetSize((580, 560))

    # -------------------------------------------------------------
    # Tab 1: Camouflage
    # -------------------------------------------------------------
    # -------------------------------------------------------------
    # Tab 1: Camouflage (Step-by-Step Layering Workflow)
    # -------------------------------------------------------------
    def BuildCamoTab(self, panel):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Step 1: Silkscreen Stash & Protect ---
        step1_box = wx.StaticBoxSizer(wx.StaticBox(panel, wx.ID_ANY, "Step 1: Existing Silkscreen Stash & Protect"), wx.VERTICAL)
        step1_desc = wx.StaticText(
            panel,
            label="Hide component references (R1, C1, etc.) and stash board silkscreen\n"
                  "so they don't clash with camouflage. Recorded once and protected from overwrite.",
        )
        step1_box.Add(step1_desc, 0, wx.ALL, 4)

        step1_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_step1_stash = wx.Button(panel, label="1. Stash Silkscreen (Hide R1/C1)", size=(-1, 32))
        self.btn_step1_stash.Bind(wx.EVT_BUTTON, self.OnStashSilkscreen)
        self.btn_step4_restore = wx.Button(panel, label="4. Restore Silkscreen (Revert All)", size=(-1, 32))
        self.btn_step4_restore.Bind(wx.EVT_BUTTON, self.OnRestoreSilkscreen)

        step1_btn_sizer.Add(self.btn_step1_stash, 1, wx.EXPAND | wx.RIGHT, 6)
        step1_btn_sizer.Add(self.btn_step4_restore, 1, wx.EXPAND)
        step1_box.Add(step1_btn_sizer, 0, wx.EXPAND | wx.ALL, 4)

        self.lbl_step1_status = wx.StaticText(panel, label="Silkscreen status: Normal (not stashed)")
        step1_box.Add(self.lbl_step1_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        sizer.Add(step1_box, 0, wx.EXPAND | wx.ALL, 6)

        # --- Step 2: Camouflage Pattern & Layering ---
        settings_box = wx.StaticBoxSizer(wx.StaticBox(panel, wx.ID_ANY, "Step 2: Generate & Layer Camouflage Pattern"), wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=10)
        grid.AddGrowableCol(1)

        p = self.saved_params

        # Target side
        grid.Add(wx.StaticText(panel, label="Target Layer:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.choice_side = wx.Choice(panel, choices=["Front (F.Silkscreen)", "Back (B.Silkscreen)"])
        self.choice_side.SetSelection(int(p.get("side", 0)))
        grid.Add(self.choice_side, 0, wx.EXPAND)

        # Pattern Style
        grid.Add(wx.StaticText(panel, label="Pattern Style:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.choice_pattern = wx.Choice(
            panel,
            choices=[
                "Test Mule Swirl (Automotive Vortex / Spirals)",
                "Zebra Waves (Organic Undulating Flow Stripes)",
            ],
        )
        self.choice_pattern.SetSelection(int(p.get("pattern", 0)))
        self.choice_pattern.Bind(wx.EVT_CHOICE, self.OnPatternChanged)
        grid.Add(self.choice_pattern, 0, wx.EXPAND)

        # Pattern Scale
        grid.Add(wx.StaticText(panel, label="Pattern Scale (mm):"), 0, wx.ALIGN_CENTER_VERTICAL)
        scale_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_scale_min = wx.TextCtrl(panel, value=str(p.get("scale_min", p.get("scale", "6.0"))))
        self.txt_scale_max = wx.TextCtrl(panel, value=str(p.get("scale_max", p.get("scale", "10.0"))))
        scale_sizer.Add(self.txt_scale_min, 1, wx.EXPAND)
        scale_sizer.Add(wx.StaticText(panel, label=" - "), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 4)
        scale_sizer.Add(self.txt_scale_max, 1, wx.EXPAND)
        grid.Add(scale_sizer, 0, wx.EXPAND)

        # Line Width
        grid.Add(wx.StaticText(panel, label="Line Width (mm):"), 0, wx.ALIGN_CENTER_VERTICAL)
        line_w_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_line_w_min = wx.TextCtrl(panel, value=str(p.get("line_w_min", p.get("line_width", "0.6"))))
        self.txt_line_w_max = wx.TextCtrl(panel, value=str(p.get("line_w_max", p.get("line_width", "1.0"))))
        line_w_sizer.Add(self.txt_line_w_min, 1, wx.EXPAND)
        line_w_sizer.Add(wx.StaticText(panel, label=" - "), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 4)
        line_w_sizer.Add(self.txt_line_w_max, 1, wx.EXPAND)
        grid.Add(line_w_sizer, 0, wx.EXPAND)

        # Wave Angle (for Zebra Waves: 0=Horizontal, 90=Vertical) - placed right below Line Width
        self.lbl_wave_angle = wx.StaticText(panel, label="Wave Angle (deg, 0=Horiz):")
        grid.Add(self.lbl_wave_angle, 0, wx.ALIGN_CENTER_VERTICAL)
        angle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_angle_min = wx.TextCtrl(panel, value=str(p.get("angle_min", p.get("wave_angle", "-5.0"))))
        self.lbl_angle_dash = wx.StaticText(panel, label=" - ")
        self.txt_angle_max = wx.TextCtrl(panel, value=str(p.get("angle_max", p.get("wave_angle", "5.0"))))
        angle_sizer.Add(self.txt_angle_min, 1, wx.EXPAND)
        angle_sizer.Add(self.lbl_angle_dash, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 4)
        angle_sizer.Add(self.txt_angle_max, 1, wx.EXPAND)
        grid.Add(angle_sizer, 0, wx.EXPAND)

        # Pad Clearance
        grid.Add(wx.StaticText(panel, label="Pad Clearance (mm):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.txt_pad_clearance = wx.TextCtrl(panel, value=str(p.get("pad_clearance", "0.4")))
        grid.Add(self.txt_pad_clearance, 0, wx.EXPAND)

        # Board Margin
        grid.Add(wx.StaticText(panel, label="Board Edge Margin (mm):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.txt_margin = wx.TextCtrl(panel, value=str(p.get("board_margin", "0.5")))
        grid.Add(self.txt_margin, 0, wx.EXPAND)

        # Seed
        grid.Add(wx.StaticText(panel, label="Random Seed:"), 0, wx.ALIGN_CENTER_VERTICAL)
        seed_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_seed = wx.TextCtrl(panel, value=str(p.get("seed", "42")))
        btn_rand_seed = wx.Button(panel, label="New Seed", size=(80, -1))
        btn_rand_seed.Bind(wx.EVT_BUTTON, self.OnRandomSeed)
        seed_sizer.Add(self.txt_seed, 1, wx.EXPAND | wx.RIGHT, 4)
        seed_sizer.Add(btn_rand_seed, 0)
        grid.Add(seed_sizer, 0, wx.EXPAND)

        settings_box.Add(grid, 0, wx.EXPAND | wx.ALL, 4)

        # Layering Option (Default False: Add onto existing)
        self.chk_clear_existing = wx.CheckBox(
            panel, label="Clear existing camouflage before generating (Replace mode)"
        )
        self.chk_clear_existing.SetValue(bool(p.get("clear_existing", False)))
        settings_box.Add(self.chk_clear_existing, 0, wx.ALL, 4)

        # Initialize parameter enable/disable states based on current pattern
        self.OnPatternChanged()

        sizer.Add(settings_box, 1, wx.EXPAND | wx.ALL, 6)

        # Action Buttons (Step 2: Add Camo Layer / Step 3: Clear Camo)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_generate = wx.Button(panel, label="2. Add Camo Layer (重ね掛け)", size=(-1, 38))
        self.btn_generate.SetBackgroundColour(wx.Colour(50, 150, 250))
        self.btn_generate.SetForegroundColour(wx.Colour(255, 255, 255))
        self.btn_generate.Bind(wx.EVT_BUTTON, self.OnGenerateCamo)

        self.btn_clear_camo = wx.Button(panel, label="3. Clear Camo (迷彩消去)", size=(-1, 38))
        self.btn_clear_camo.Bind(wx.EVT_BUTTON, self.OnClearCamoOnly)

        btn_sizer.Add(self.btn_generate, 2, wx.EXPAND | wx.RIGHT, 6)
        btn_sizer.Add(self.btn_clear_camo, 1, wx.EXPAND)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 6)

        panel.SetSizer(sizer)

    # -------------------------------------------------------------
    # Tab 2: Silk Stash & Restore
    # -------------------------------------------------------------
    def BuildStashTab(self, panel):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Header description
        desc_box = wx.StaticBoxSizer(wx.StaticBox(panel, wx.ID_ANY, "Silkscreen Stashing"), wx.VERTICAL)
        desc = wx.StaticText(
            panel,
            label="Safely moves existing silkscreen items (texts, references, board drawings)\n"
                  "to an unused user layer (scanned backwards: User.9 -> User.8 -> ... -> User.1)\n"
                  "so they don't clash with the camouflage, and restores them anytime.",
        )
        desc_box.Add(desc, 0, wx.ALL, 5)
        sizer.Add(desc_box, 0, wx.EXPAND | wx.ALL, 6)

        # Stash Control
        stash_box = wx.StaticBoxSizer(wx.StaticBox(panel, wx.ID_ANY, "Layer Controls"), wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
        grid.AddGrowableCol(1)

        # Target side
        grid.Add(wx.StaticText(panel, label="Silkscreen Side:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.choice_stash_side = wx.Choice(panel, choices=["Front (F.Silkscreen)", "Back (B.Silkscreen)"])
        self.choice_stash_side.SetSelection(0)
        grid.Add(self.choice_stash_side, 0, wx.EXPAND)

        # Detected Free Layer
        grid.Add(wx.StaticText(panel, label="Stash Destination Layer:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.choice_target_layer = wx.Choice(panel, choices=[])
        self.RefreshUserLayerChoices()
        grid.Add(self.choice_target_layer, 0, wx.EXPAND)

        stash_box.Add(grid, 0, wx.EXPAND | wx.ALL, 6)

        # Refresh scan button
        btn_refresh_layers = wx.Button(panel, label="Rescan Available User Layers")
        btn_refresh_layers.Bind(wx.EVT_BUTTON, lambda e: self.RefreshUserLayerChoices())
        stash_box.Add(btn_refresh_layers, 0, wx.ALL, 6)

        sizer.Add(stash_box, 0, wx.EXPAND | wx.ALL, 6)

        # Stash / Restore Buttons
        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_stash = wx.Button(panel, label="Stash Silkscreen (Move)", size=(-1, 36))
        self.btn_stash.Bind(wx.EVT_BUTTON, self.OnStashSilkscreen)

        self.btn_restore = wx.Button(panel, label="Restore Silkscreen (Revert)", size=(-1, 36))
        self.btn_restore.Bind(wx.EVT_BUTTON, self.OnRestoreSilkscreen)

        btn_box.Add(self.btn_stash, 1, wx.EXPAND | wx.RIGHT, 6)
        btn_box.Add(self.btn_restore, 1, wx.EXPAND)
        sizer.Add(btn_box, 0, wx.EXPAND | wx.ALL, 6)

        # Item Counts info
        self.lbl_stash_info = wx.StaticText(panel, label="")
        sizer.Add(self.lbl_stash_info, 1, wx.EXPAND | wx.ALL, 8)
        self.UpdateStashStatus()

        panel.SetSizer(sizer)

    # -------------------------------------------------------------
    # Event Handlers & Helpers
    # -------------------------------------------------------------
    def OnRandomSeed(self, event):
        self.txt_seed.SetValue(str(random.randint(1, 99999)))

    def RefreshUserLayerChoices(self):
        """Populate the target layer dropdown, prioritizing User.9 down to User.1."""
        self.board = pcbnew.GetBoard()
        self.stash_mgr = SilkStashManager(self.board)

        candidates = get_user_layer_candidates()
        choices = []
        self.layer_id_map = []

        recommended_idx = 0
        free_layer_id, _ = find_unused_user_layer(self.board)

        for i, (layer_id, name) in enumerate(candidates):
            current_name = self.board.GetLayerName(layer_id)
            count = self.stash_mgr.count_items_on_layer(layer_id)
            status = f"[FREE]" if count == 0 else f"[{count} items]"
            label = f"{name} ({current_name}) - {status}"
            choices.append(label)
            self.layer_id_map.append(layer_id)

            if layer_id == free_layer_id:
                recommended_idx = i

        self.choice_target_layer.Set(choices)
        if choices:
            self.choice_target_layer.SetSelection(recommended_idx)

    def UpdateStashStatus(self):
        """Update count of items on silkscreen and candidate stash layers."""
        self.board = pcbnew.GetBoard()
        f_count = self.stash_mgr.count_items_on_layer(LAYER_F_SILK)
        b_count = self.stash_mgr.count_items_on_layer(LAYER_B_SILK)
        text = f"Current Silkscreen: F.Silkscreen ({f_count} items), B.Silkscreen ({b_count} items)"
        self.lbl_stash_info.SetLabel(text)

        if hasattr(self, "lbl_step1_status"):
            if self.hidden_uuids or self.last_stashed_layer is not None:
                cnt = len(self.hidden_uuids)
                self.lbl_step1_status.SetLabel(f"Silkscreen status: STASHED & PROTECTED ({cnt} items hidden)")
                self.lbl_step1_status.SetForegroundColour(wx.Colour(0, 140, 60))
            else:
                self.lbl_step1_status.SetLabel("Silkscreen status: Normal (displayed on PCB)")
                self.lbl_step1_status.SetForegroundColour(wx.Colour(80, 80, 80))
            self.lbl_step1_status.Refresh()

    def OnPatternChanged(self, event=None):
        """Update parameter availability based on selected pattern style."""
        # Selection 0: Swirl (doesn't use wave_angle)
        # Selection 1: Zebra (uses wave_angle)
        is_zebra = (self.choice_pattern.GetSelection() == 1) if hasattr(self, "choice_pattern") else False
        if hasattr(self, "lbl_wave_angle"):
            self.lbl_wave_angle.Enable(is_zebra)
        if hasattr(self, "txt_angle_min"):
            self.txt_angle_min.Enable(is_zebra)
        if hasattr(self, "lbl_angle_dash"):
            self.lbl_angle_dash.Enable(is_zebra)
        if hasattr(self, "txt_angle_max"):
            self.txt_angle_max.Enable(is_zebra)
        if event:
            self.SaveConfig()
            event.Skip()

    def OnGenerateCamo(self, event):
        self.board = pcbnew.GetBoard()
        self.camo_gen = CamoGenerator(self.board)
        self.stash_mgr = SilkStashManager(self.board)

        side = "F" if self.choice_side.GetSelection() == 0 else "B"

        pattern_idx = self.choice_pattern.GetSelection()
        pattern_types = ["swirl", "zebra"]
        pattern_type = pattern_types[pattern_idx]

        try:
            scale_min = float(self.txt_scale_min.GetValue())
            scale_max = float(self.txt_scale_max.GetValue())
            scale_range = (min(scale_min, scale_max), max(scale_min, scale_max))

            line_w_min = float(self.txt_line_w_min.GetValue())
            line_w_max = float(self.txt_line_w_max.GetValue())
            line_w_range = (min(line_w_min, line_w_max), max(line_w_min, line_w_max))

            angle_min = float(self.txt_angle_min.GetValue())
            angle_max = float(self.txt_angle_max.GetValue())
            angle_range = (min(angle_min, angle_max), max(angle_min, angle_max))

            pad_clr_mm = float(self.txt_pad_clearance.GetValue())
            margin_mm = float(self.txt_margin.GetValue())
            seed = int(self.txt_seed.GetValue())
        except ValueError:
            wx.MessageBox("Please enter valid numerical parameters.", "Input Error", wx.ICON_ERROR)
            return

        # If clear existing requested, remove existing camo shapes before generating
        if self.chk_clear_existing.IsChecked():
            self.camo_gen.remove_all_camo_shapes(side=side, target_uuids=self.camo_shape_uuids)
            self.camo_shape_uuids = []
            layer_uuids = None
        else:
            layer_uuids = self.camo_shape_uuids

        # Generate camo layer with automatic seamless merging
        try:
            count, created_uuids = self.camo_gen.generate_camouflage(
                side=side,
                pattern_type=pattern_type,
                scale_range=scale_range,
                line_w_range=line_w_range,
                angle_range=angle_range,
                pad_clearance_mm=pad_clr_mm,
                board_margin_mm=margin_mm,
                seed=seed,
                existing_uuids=layer_uuids,
            )
            self.camo_shape_uuids = created_uuids
            self.SaveConfig()

            # Auto-advance seed for the next layer
            self.txt_seed.SetValue(str(random.randint(1, 99999)))

            total_camo = len(self.camo_shape_uuids)
            msg = f"Layer merged: {total_camo} unified shapes on {side}.Silkscreen"
            self.lbl_status.SetLabel(msg)
            self.UpdateStashStatus()
            self.RefreshUserLayerChoices()
        except Exception as e:
            wx.MessageBox(f"Error generating camouflage: {e}", "Generation Error", wx.ICON_ERROR)

    def OnClearCamoOnly(self, event):
        """Step 3: Remove only camouflage shapes without touching stashed silkscreen."""
        self.board = pcbnew.GetBoard()
        self.camo_gen = CamoGenerator(self.board)
        side = "F" if self.choice_side.GetSelection() == 0 else "B"

        removed = self.camo_gen.remove_all_camo_shapes(side=side, target_uuids=self.camo_shape_uuids)
        self.camo_shape_uuids = []
        self.SaveConfig()

        self.lbl_status.SetLabel(f"Cleared {removed} camouflage shapes. Silkscreen remains stashed.")

    def OnStashSilkscreen(self, event):
        """Step 1: Stash silkscreen. Hides visible references and stashes board graphics."""
        self.board = pcbnew.GetBoard()
        self.stash_mgr = SilkStashManager(self.board)
        side = "F" if self.choice_side.GetSelection() == 0 else "B"

        # Verify against actual board state (auto-clean if board was closed without saving)
        self.VerifyAndSanitizeStashState()

        sel_idx = self.choice_target_layer.GetSelection() if hasattr(self, "choice_target_layer") else -1
        target_layer_id = self.layer_id_map[sel_idx] if sel_idx >= 0 else None

        try:
            res = self.stash_mgr.stash_silkscreen(side=side, target_layer_id=target_layer_id)
            self.last_stashed_layer = res["target_layer_id"]
            # Accumulate newly hidden UUIDs without losing existing ones
            new_uids = set(self.hidden_uuids).union(res.get("hidden_uuids", []))
            self.hidden_uuids = list(new_uids)
            self.SaveConfig()

            self.lbl_status.SetLabel(
                f"Stashed {res['count']} items from {side}.Silkscreen into {res['target_layer_name']}."
            )
            self.UpdateStashStatus()
            self.RefreshUserLayerChoices()
        except Exception as e:
            wx.MessageBox(f"Failed to stash silkscreen: {e}", "Error", wx.ICON_ERROR)

    def OnRestoreSilkscreen(self, event):
        self.board = pcbnew.GetBoard()
        self.stash_mgr = SilkStashManager(self.board)
        side = "F" if self.choice_stash_side.GetSelection() == 0 else "B"

        sel_idx = self.choice_target_layer.GetSelection()
        source_layer_id = self.layer_id_map[sel_idx] if sel_idx >= 0 else self.last_stashed_layer

        try:
            count = self.stash_mgr.restore_silkscreen(
                source_layer_id=source_layer_id,
                target_side=side,
                hidden_uuids=self.hidden_uuids,
            )
            self.hidden_uuids = []
            self.SaveConfig()

            self.lbl_status.SetLabel(f"Restored {count} items back to {side}.Silkscreen.")
            self.UpdateStashStatus()
            self.RefreshUserLayerChoices()
        except Exception as e:
            wx.MessageBox(f"Failed to restore silkscreen: {e}", "Error", wx.ICON_ERROR)
