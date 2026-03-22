# core/ui_components.py
import customtkinter as ctk
from .constants import CARD_BG, CORNER_RADIUS_INNER, CARD_BORDER

def create_card(parent):
    """Creates a standardized card frame with glassmorphism border."""
    return ctk.CTkFrame(
        parent, 
        fg_color=CARD_BG, 
        corner_radius=CORNER_RADIUS_INNER, 
        border_width=1, 
        border_color=CARD_BORDER
    )
