"""
Silk Stash & Restore Module for KiCad PCB Editor.
Safely moves existing silkscreen items (board drawings, texts, and footprint elements)
to an unused User layer (searching backwards from User.9 down to User.3)
and restores them back whenever needed.
"""

import pcbnew

# Safe layer ID definitions across KiCad versions (F_SilkS, B_SilkS)
LAYER_F_SILK = getattr(pcbnew, "F_SilkS", getattr(pcbnew, "F_Silkscreen", 37))
LAYER_B_SILK = getattr(pcbnew, "B_SilkS", getattr(pcbnew, "B_Silkscreen", 36))


def get_item_uuid(item):
    """Safely get string representation of UUID from a KiCad board item."""
    if hasattr(item, "m_Uuid"):
        return item.m_Uuid.AsString()
    elif hasattr(item, "GetUuid"):
        return item.GetUuid().AsString()
    return ""


# User layers in KiCad (User.9 down to User.1)
# In KiCad 7/8/9, User_1 to User_9 have corresponding layer IDs.
def get_user_layer_candidates():
    """Return user layer IDs in reverse order: User.9 -> User.8 -> ... -> User.3"""
    candidates = []
    # Layer name mapping from User.9 to User.1
    for i in range(9, 0, -1):
        attr_name = f"User_{i}"
        if hasattr(pcbnew, attr_name):
            candidates.append((getattr(pcbnew, attr_name), f"User.{i}"))
    return candidates


def find_unused_user_layer(board, exclude_layers=None):
    """
    Search backwards from User.9 down to User.1 for a layer that has no items on it.
    Returns (layer_id, layer_original_name) or None if all are used.
    """
    if exclude_layers is None:
        exclude_layers = set()

    candidates = get_user_layer_candidates()
    
    # Collect all layers currently containing items on the board
    used_layers = set()
    
    # 1. Check board-level drawings
    for drawing in board.GetDrawings():
        used_layers.add(drawing.GetLayer())

    # 2. Check footprint graphical items and texts
    for fp in board.GetFootprints():
        try:
            if hasattr(fp, "Reference") and fp.Reference():
                used_layers.add(fp.Reference().GetLayer())
            if hasattr(fp, "Value") and fp.Value():
                used_layers.add(fp.Value().GetLayer())
        except Exception:
            pass

        # Graphical items inside footprint
        try:
            for item in fp.GraphicalItems():
                used_layers.add(item.GetLayer())
        except Exception:
            pass

    # 3. Check tracks and vias
    for track in board.GetTracks():
        used_layers.add(track.GetLayer())

    # Find first candidate not in used_layers and not in exclude_layers
    for layer_id, layer_name in candidates:
        if layer_id not in used_layers and layer_id not in exclude_layers:
            return layer_id, layer_name

    # If all 9..1 have items, fallback to User.9
    for layer_id, layer_name in candidates:
        if layer_id not in exclude_layers:
            return layer_id, layer_name

    return None, None


class SilkStashManager:
    """Manages stashing and restoring silkscreen items to/from unused user layers."""

    def __init__(self, board):
        self.board = board

    def get_silk_layers(self, side="both"):
        """Get list of silkscreen layer IDs based on side ('F', 'B', or 'both')."""
        layers = []
        if side in ("F", "both"):
            layers.append(LAYER_F_SILK)
        if side in ("B", "both"):
            layers.append(LAYER_B_SILK)
        return layers

    def stash_silkscreen(self, side="both", target_layer_id=None):
        """
        Move silkscreen items to an unused user layer.
        Returns dict with details: {'count': N, 'target_layer_id': id, 'target_layer_name': name}
        """
        silk_layers = self.get_silk_layers(side)
        if not silk_layers:
            return {"count": 0, "target_layer_id": None, "target_layer_name": None}

        # Find target layer if not explicitly specified
        if target_layer_id is None:
            target_layer_id, orig_name = find_unused_user_layer(self.board)
            if target_layer_id is None:
                raise RuntimeError("No available User layers (User.9..User.1) found for stashing.")
        else:
            orig_name = self.board.GetLayerName(target_layer_id)

        # Set a clear custom layer name in board setup if supported
        custom_name = f"Camo_Stash_{side}"
        try:
            self.board.SetLayerName(target_layer_id, custom_name)
        except Exception:
            pass

        # Ensure the layer is enabled/visible
        try:
            enabled = self.board.GetEnabledLayers()
            enabled.set(target_layer_id, True)
            self.board.SetEnabledLayers(enabled)
        except Exception:
            pass

        count = 0
        hidden_uuids = []

        # 1. Stash board-level drawings (PCB_SHAPE, PCB_TEXT) to user layer
        for drawing in self.board.GetDrawings():
            if drawing.GetLayer() in silk_layers:
                drawing.SetLayer(target_layer_id)
                count += 1

        # 2. Hide footprint-level Reference and Value (keeps layer intact to prevent DRC errors)
        for fp in self.board.GetFootprints():
            # Reference
            try:
                ref = fp.Reference()
                if ref and ref.GetLayer() in silk_layers and ref.IsVisible():
                    uid = get_item_uuid(ref)
                    if uid:
                        hidden_uuids.append(uid)
                    ref.SetVisible(False)
                    count += 1
            except Exception:
                pass

            # Value
            try:
                val = fp.Value()
                if val and val.GetLayer() in silk_layers and val.IsVisible():
                    uid = get_item_uuid(val)
                    if uid:
                        hidden_uuids.append(uid)
                    val.SetVisible(False)
                    count += 1
            except Exception:
                pass

        # Refresh board
        pcbnew.Refresh()

        return {
            "count": count,
            "target_layer_id": target_layer_id,
            "target_layer_name": custom_name or orig_name,
            "hidden_uuids": hidden_uuids,
        }

    def restore_silkscreen(self, source_layer_id, target_side="F", hidden_uuids=None):
        """
        Restore items from a stashed layer back to their original silkscreen layer,
        and unhide only previously hidden footprint text items.
        target_side: 'F' -> LAYER_F_SILK, 'B' -> LAYER_B_SILK
        hidden_uuids: List or Set of UUID strings recorded when stashed
        Returns number of items restored.
        """
        target_layer = LAYER_F_SILK if target_side == "F" else LAYER_B_SILK
        count = 0
        hidden_set = set(hidden_uuids or [])
        # If no specific UUIDs were recorded, unhide all hidden items on target silkscreen layer
        restore_all_if_empty = len(hidden_set) == 0

        # 1. Restore board-level drawings from user layer
        if source_layer_id is not None:
            for drawing in self.board.GetDrawings():
                if drawing.GetLayer() == source_layer_id:
                    drawing.SetLayer(target_layer)
                    count += 1

        # 2. Restore footprint references & values
        for fp in self.board.GetFootprints():
            # Restore visibility for references
            try:
                ref = fp.Reference()
                if ref and ref.GetLayer() == target_layer:
                    uid = get_item_uuid(ref)
                    should_restore = (uid in hidden_set) or (restore_all_if_empty and not ref.IsVisible())
                    if should_restore or (source_layer_id and ref.GetLayer() == source_layer_id):
                        if not ref.IsVisible():
                            ref.SetVisible(True)
                            count += 1
                        if source_layer_id and ref.GetLayer() == source_layer_id:
                            ref.SetLayer(target_layer)
            except Exception:
                pass

            # Restore visibility for values
            try:
                val = fp.Value()
                if val and val.GetLayer() == target_layer:
                    uid = get_item_uuid(val)
                    should_restore = (uid in hidden_set) or (restore_all_if_empty and not val.IsVisible())
                    if should_restore or (source_layer_id and val.GetLayer() == source_layer_id):
                        if not val.IsVisible():
                            val.SetVisible(True)
                            count += 1
                        if source_layer_id and val.GetLayer() == source_layer_id:
                            val.SetLayer(target_layer)
            except Exception:
                pass

            # Fallback for footprint graphical items if previously moved
            try:
                if source_layer_id is not None:
                    for item in fp.GraphicalItems():
                        if item.GetLayer() == source_layer_id:
                            item.SetLayer(target_layer)
                            count += 1
            except Exception:
                pass

        pcbnew.Refresh()
        return count

    def count_items_on_layer(self, layer_id):
        """Count how many drawings / texts / footprint items currently reside on the given layer."""
        count = 0
        for drawing in self.board.GetDrawings():
            if drawing.GetLayer() == layer_id:
                count += 1

        for fp in self.board.GetFootprints():
            try:
                if fp.Reference() and fp.Reference().GetLayer() == layer_id:
                    count += 1
                if fp.Value() and fp.Value().GetLayer() == layer_id:
                    count += 1
                for item in fp.GraphicalItems():
                    if item.GetLayer() == layer_id:
                        count += 1
            except Exception:
                pass

        return count
